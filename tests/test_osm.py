"""app.ingest.osm.summarize_context — pure function, no network."""

from app.ingest.osm import summarize_context


def test_returns_none_for_no_elements():
    assert summarize_context([]) is None


def test_names_a_single_entrance():
    note = summarize_context([{"entrance": "yes", "name": "West Gate"}])
    assert note == "Named entrance nearby: West Gate."


def test_dedupes_repeated_entrance_names():
    elements = [{"entrance": "yes", "name": "West Gate"}, {"entrance": "yes", "name": "West Gate"}]
    note = summarize_context(elements)
    assert note.count("West Gate") == 1


def test_combines_entrance_bike_parking_and_elevator():
    elements = [
        {"entrance": "yes", "name": "Main Gate"},
        {"amenity": "bicycle_parking"},
        {"highway": "elevator"},
    ]
    note = summarize_context(elements)
    assert "Main Gate" in note
    assert "Bicycle parking nearby." in note
    assert "Elevator access nearby." in note


def test_ignores_unnamed_entrance():
    # entrance=yes with no name isn't worth mentioning by itself.
    assert summarize_context([{"entrance": "yes", "name": None}]) is None
