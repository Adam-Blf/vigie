"""J12 quantization study: fp32 against int8 for the embedding model, Q4 against Q8 for the LLM.

Only the decision, the statistics and the dense search are imported eagerly. ONNX export,
onnxruntime sessions, MLflow and matplotlib live behind the ``quant`` and ``tracking``
extras and are imported inside the functions that need them, so the API image never pays
for them.
"""
