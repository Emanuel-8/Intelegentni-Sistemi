"""
export_ai_weights.py
─────────────────────────────────────────────────────────────
Converts the trained Stable-Baselines3 model (p2_ai.zip) into a
tiny numpy file (p2_ai_weights.npz) that the game can run WITHOUT
PyTorch or Stable-Baselines3 installed.

Players only need pygame + numpy. Torch is needed for training only.

Run after every training session:
    python export_ai_weights.py            (reads p2_ai.zip)
    python export_ai_weights.py other.zip  (any SB3 PPO MlpPolicy zip)

This reads the PyTorch checkpoint format directly (it is a zip of a
pickle + raw float buffers), so torch does not need to be installed.
"""

import io
import os
import pickle
import sys
import zipfile

import numpy as np

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

_DTYPES = {
    "FloatStorage": np.float32,
    "DoubleStorage": np.float64,
    "HalfStorage": np.float16,
    "LongStorage": np.int64,
    "IntStorage": np.int32,
}


def _load_torch_state_dict(pth_bytes):
    """Minimal reader for torch.save() zip checkpoints (tensors only)."""
    zf = zipfile.ZipFile(io.BytesIO(pth_bytes))
    names = zf.namelist()
    pkl_name = next(n for n in names if n.endswith("data.pkl"))
    prefix = pkl_name[: -len("data.pkl")]

    class _Storage:
        def __init__(self, dtype, key):
            self.dtype, self.key = dtype, key

    def _rebuild_tensor(storage, offset, size, stride, *_):
        raw = zf.read(f"{prefix}data/{storage.key}")
        flat = np.frombuffer(raw, dtype=storage.dtype)
        itemsize = flat.itemsize
        return np.lib.stride_tricks.as_strided(
            flat[offset:], shape=tuple(size),
            strides=tuple(s * itemsize for s in stride)).copy()

    class _Unpickler(pickle.Unpickler):
        def find_class(self, module, name):
            if module == "torch._utils" and name == "_rebuild_tensor_v2":
                return _rebuild_tensor
            if module == "torch" and name in _DTYPES:
                return _DTYPES[name]
            if module == "collections" and name == "OrderedDict":
                import collections
                return collections.OrderedDict
            raise pickle.UnpicklingError(f"unsupported global {module}.{name}")

        def persistent_load(self, pid):
            # ('storage', storage_type, key, location, numel)
            _, dtype, key, _loc, _numel = pid
            return _Storage(dtype, key)

    return _Unpickler(io.BytesIO(zf.read(pkl_name))).load()


def export(zip_path, out_path):
    with zipfile.ZipFile(zip_path) as zf:
        state = _load_torch_state_dict(zf.read("policy.pth"))
    layers = {}
    i = 0
    while f"mlp_extractor.policy_net.{i}.weight" in state:
        n = len(layers) // 2
        layers[f"w{n}"] = state[f"mlp_extractor.policy_net.{i}.weight"]
        layers[f"b{n}"] = state[f"mlp_extractor.policy_net.{i}.bias"]
        i += 2   # Linear, Tanh, Linear, Tanh ...
    n = len(layers) // 2
    layers[f"w{n}"] = state["action_net.weight"]
    layers[f"b{n}"] = state["action_net.bias"]
    np.savez(out_path, **layers)
    shapes = ", ".join(f"{k}{v.shape}" for k, v in layers.items() if k.startswith("w"))
    print(f"Exported {n + 1} layers [{shapes}] -> {out_path}")


if __name__ == "__main__":
    src = sys.argv[1] if len(sys.argv) > 1 else os.path.join(SCRIPT_DIR, "p2_ai.zip")
    dst = os.path.join(SCRIPT_DIR, "p2_ai_weights.npz")
    export(src, dst)
