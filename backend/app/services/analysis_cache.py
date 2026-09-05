"""
The analysis cache key, in one place.

It was built in four files in three different shapes, and the drift was not
theoretical: the nightly job warmed one key while the frontend read another, so
every race view regenerated a full analysis for weeks. Two more readers
(edge_board and the debrief path) still build shorter keys that can never match
anything the nightly writes.

Every segment matters. mode and experience level change the generated content;
the fingerprint invalidates the entry when the race data moves.
"""

# What the nightly job locks under. The frontend's defaults must match these or
# the warmed analysis is never served — see RaceDetailPage's analysisMode and
# the store's experienceLevel default.
LOCK_MODE = "medium"
LOCK_EXPERIENCE = "beginner"


def analysis_cache_key(race_id: str, mode: str = LOCK_MODE,
                       experience: str | None = None, fingerprint: str = "") -> str:
    """The one true key. `experience` None means the caller did not specify one,
    which the API records as "default"."""
    return f"ai_analysis:{race_id}:{mode}:{experience or 'default'}:{fingerprint}"
