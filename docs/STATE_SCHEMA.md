# State Schema (MVP)

## Required
- user_id: string
- current_level: number
- total_exp: number
- daily_exp: number
- streak: number
- chat_history: array

## Optional (from AI)
- current_focus: string|null
- current_plan: string|array|null
- current_do_now: string|null
- memory_note: string|null

## Business rules
- daily_exp <= 140
- level = floor(1 + sqrt(total_exp / 100))
- keep required keys always present