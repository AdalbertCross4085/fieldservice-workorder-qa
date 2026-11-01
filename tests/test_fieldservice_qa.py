from src.fieldservice_qa import Question, choose_follow_up


def test_blocked_dispatch_goes_to_coordinator():
    result = choose_follow_up(
        Question("WO-1042", "Why is the repair waiting?"),
        [{"metadata": {"dispatch_status": "awaiting_parts", "photo_url": "https://photos.example/wo-1042.jpg"}}],
    )
    assert result["action"] == "dispatch_coordinator"


def test_missing_photo_requests_site_photo():
    result = choose_follow_up(Question("WO-1043", "Show the repair evidence"), [{"metadata": {"dispatch_status": "en_route"}}])
    assert result["action"] == "request_site_photo"
