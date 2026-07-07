"""
brain_modules/layers/
Ordered pipeline layers for brain.think().

Each layer is a module with a single process(ctx, deps) function
that returns a LayerResult.

Load order is defined in brain_modules/pipeline.py LAYER_ORDER.
"""