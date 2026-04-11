"""Role package.

Import role modules explicitly from ``vibe3.roles.<name>`` so the runtime and
tests always depend on the concrete role file rather than package-level
re-export shims.
"""
