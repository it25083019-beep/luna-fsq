# Career + RPG orientation (chin chu design)

## Principle
Do **not** store every job/hobby in the world.
Map free text → **personality axes** → **career clusters** → RPG class.

Unknown interests still work:
1. Keyword/axis match when possible
2. Else boost explore axis
3. Always return top clusters + exploration route
4. Gemini can later rewrite example job titles only (labels), not change taxonomy

## API
- GET /career/taxonomy
- POST /career/suggest body example:
`json
{
  "decided_career": null,
  "personality_text": "一人で黙々と作りたい",
  "hobbies_text": "VTuberの3Dモデリング",
  "favorite_subjects": ["art", "cs"],
  "subject_grades": {"cs": 4, "art": 5},
  "save": true
}
`
- POST /career/select { "cluster_id": "design_creative" }
- GET /career/me

## HTML demo link
d:/usbreco/future_skill_quest_demo.html = UI vision for class/skills/quests/boss/portfolio.
Backend career engine feeds that vision with real suggestion data.
