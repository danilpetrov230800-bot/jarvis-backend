def test_stress_messages(client):
    for i in range(120):
        r = client.post("/api/chat", json={"text": f"посчитай {i}+{i}"})
        assert r.status_code == 200
        assert r.json()["reply"]


def test_many_skills_and_memory(client):
    for i in range(40):
        client.post("/api/skills", json={"name": f"skill-{i}", "trigger": f"триггер {i}", "actions": []})
        client.post("/api/memory", json={"content": f"факт {i}", "kind": "long_term"})
    skills = client.get("/api/skills").json()["skills"]
    mem = client.get("/api/memory").json()["items"]
    assert len(skills) >= 40
    assert len(mem) >= 40


def test_repeated_wake(client):
    for _ in range(25):
        r = client.post("/api/wake", json={"text": "Нова"})
        assert r.json()["wake"] is True
