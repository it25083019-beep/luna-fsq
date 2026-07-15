# RPG Learning Loop

Maps real study → mini RPG progress → portfolio.

| Real life | RPG |
|---|---|
| Homework / daily study | Quest (homework, daily_study) |
| Pop quiz | Treasure (pop_quiz) |
| Unit test | Equipment (unit_test) |
| Midterm / Final | Boss (midterm, inal_exam) |
| Level / regions | Travel map unlock |

## API
- GET /rpg/world — regions + quest types
- GET /rpg/me — current RPG state
- POST /rpg/quest/start — { "title", "quest_type", "subject" }
- POST /rpg/activity/complete — complete homework/quiz/exam/boss
- GET /rpg/portfolio — auto story + logs for future CV

## Example
`json
POST /rpg/activity/complete
{
  "title": "数学ドリル 20問",
  "quest_type": "homework",
  "subject": "math"
}
`
`json
POST /rpg/activity/complete
{
  "title": "英語期末テスト",
  "quest_type": "final_exam",
  "subject": "english",
  "score": 88
}
`
