"""Hamburg CityConfig subpackage. Re-exports the public symbols current
consumers import by name so `from app.cities.hamburg import ...` keeps
working with zero touch on routes/tests/inference templates. Adding a
new public symbol here means a call site is about to import it — pin
it in __all__ below so this file and the caller stay in sync."""
from app.cities.hamburg.config      import HAMBURG
from app.cities.hamburg.lenses      import NEWCOMER_LENS, COMMUTER_LENS
from app.cities.hamburg.directories import OTHERS_ADMIN_CARDS

__all__ = ["HAMBURG", "NEWCOMER_LENS", "COMMUTER_LENS", "OTHERS_ADMIN_CARDS"]
