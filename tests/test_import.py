# tests/test_import.py — admin CSV import / export of the word bank.
import csv
import io

from app import importer

TOPICS = [
    {"id": 1, "slug": "animals", "name": "Animals"},
    {"id": 2, "slug": "home", "name": "Home & furniture"},
]
HEADER = "word,meaning_vi,part_of_speech,example,usage_note,topic\n"


def test_parse_reads_every_column():
    rows, errors = importer.parse(
        HEADER + 'dog,con chó,n,"The dog barks, loudly.",,animals\n', TOPICS
    )
    assert errors == []
    assert rows == [{
        "word": "dog", "meaning_vi": "con chó", "part_of_speech": "noun",
        "example": "The dog barks, loudly.", "usage_note": None, "topic_id": 1,
    }]


def test_parse_accepts_topic_names_bom_and_blank_lines():
    text = "﻿" + HEADER + "sofa,ghế sofa,,,,Home & furniture\n\n,,,,,\n"
    rows, errors = importer.parse(text, TOPICS)
    assert errors == []
    assert [(r["word"], r["topic_id"]) for r in rows] == [("sofa", 2)]


def test_parse_reports_each_bad_line():
    text = HEADER + (
        "dog,con chó,,,,\n"  # line 2: fine
        ",trống,,,,\n"  # line 3
        "cat,,,,,\n"  # line 4
        "fox,con cáo,animal,,,\n"  # line 5
        "owl,con cú,,,,birds\n"  # line 6
        "DOG,chó,,,,\n"  # line 7: same word as line 2
    )
    rows, errors = importer.parse(text, TOPICS)
    assert [r["word"] for r in rows] == ["dog"]
    assert [(e["line"], e["message"]) for e in errors] == [
        (3, "word is empty"),
        (4, "meaning_vi is empty"),
        (5, 'unknown part_of_speech "animal"'),
        (6, 'unknown topic "birds"'),
        (7, '"DOG" is already on line 2'),
    ]


def test_parse_needs_the_header():
    try:
        importer.parse("dog,con chó\n", TOPICS)
    except importer.BadCsv as err:
        assert "header" in str(err)
    else:
        raise AssertionError("expected BadCsv")


def post(client, text, **options):
    return client.post("/api/admin/import", json={"csv": text, **options})


def test_preview_saves_nothing(client):
    r = post(client, HEADER + "dog,con chó,,,,animals\n")
    assert r.status_code == 200
    body = r.json()
    assert (body["saved"], body["total"], body["new"], body["existing"]) == (False, 1, 1, 0)
    assert client.get("/api/words").json() == []


def test_import_adds_new_and_skips_existing(client):
    client.post("/api/words", json={"word": "dog", "meaning_vi": "chó"})
    r = post(client, HEADER + "dog,con chó,,,,\ncat,con mèo,,,,\n", dry_run=False)
    assert r.json()["saved"] is True
    words = {w["word"]: w["meaning_vi"] for w in client.get("/api/words").json()}
    assert words == {"dog": "chó", "cat": "con mèo"}  # dog kept as it was


def test_import_can_update_existing(client):
    client.post("/api/words", json={"word": "dog", "meaning_vi": "chó"})
    post(client, HEADER + "Dog,con chó,n,,,animals\n", dry_run=False, update_existing=True)
    dog = client.get("/api/words").json()[0]
    assert (dog["word"], dog["meaning_vi"], dog["topic_id"]) == ("dog", "con chó", 1)


def test_file_with_errors_is_not_saved(client):
    r = post(client, HEADER + "dog,con chó,,,,\ncat,,,,,\n", dry_run=False)
    assert r.status_code == 422
    assert client.get("/api/words").json() == []


def test_bad_header_is_a_clear_error(client):
    r = post(client, "english,vietnamese\ndog,chó\n")
    assert r.status_code == 422
    assert "header" in r.json()["detail"]


def test_import_and_export_are_admin_only(learner):
    assert post(learner, HEADER + "dog,con chó,,,,\n").status_code == 403
    assert learner.get("/api/admin/words.csv").status_code == 403


def test_export_round_trips(client):
    client.post("/api/words", json={"word": "dog", "meaning_vi": "con chó, chó", "topic_id": 1})
    r = client.get("/api/admin/words.csv")
    assert r.headers["content-type"].startswith("text/csv")
    text = r.content.decode("utf-8-sig")
    assert list(csv.DictReader(io.StringIO(text))) == [{
        "word": "dog", "meaning_vi": "con chó, chó", "part_of_speech": "",
        "example": "", "usage_note": "", "topic": "animals",
    }]
    # The exported file can be imported again as it is.
    assert post(client, r.content.decode("utf-8")).json()["errors"] == []
