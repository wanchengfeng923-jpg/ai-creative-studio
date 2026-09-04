"""Creative Studio package marker.

The package initializer is intentionally side-effect free.  In particular, importing
``creative_studio.ai_v2`` must not eagerly load the retired AI modules or their
configuration and network dependencies.
"""

__all__: list[str] = []
