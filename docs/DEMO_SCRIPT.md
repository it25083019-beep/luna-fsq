# Demo Script (60-90s)

1. Call POST /checkin/morning
   body: {"user_id":"u_demo","goal":"hoc 2 pomodoro"}

2. Call POST /chat
   body: {"user_id":"u_demo","message":"Lap ke hoach hoc toi nay"}

3. Call GET /state/u_demo
   show: plan + exp + level

4. Call POST /checkin/evening
   body: {"user_id":"u_demo"}

5. Call GET /state/u_demo again
   show: total_exp updated