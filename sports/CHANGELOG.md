# Changelog

## 2.0.0
- Ten sports, one per screen: Football, Cricket, Rugby union, Tennis, Formula 1, Golf, American football,
  Basketball, Ice hockey and Baseball. The sport is always called "Football", and American football is always "American football".
- Team sports from TheSportsDB Premium (next, result, and live scores for American football, basketball, ice hockey
  and baseball). Cricket's result in words. Overtime said.
- Formula 1 from Jolpica-F1, with no key: the next race with a countdown, the last podium, the drivers' standings,
  and a driver to pick out.
- Tennis and golf: a tour's current or next tournament, then its winner, and a player to pick out.
- A new screen style, Games: a countdown to the Olympics and Paralympics (LA 2028, French Alps 2030), DAY n OF m
  while they are on, then the next. No key; no medal table.
- Each source's key entered once for every Sports screen: Key (football-data.org) and Premium key (TheSportsDB).
  TheSportsDB's free key isn't offered (it is "123", a shared test key, and too little).
- An icon for each sport, and the Games' torch, sun and snowflake, as Animator projects in `art/`.
- Older settings load as they were: a 1.x screen is a football screen with its team, views and source.
- **The one step for a 1.x user whose screens used TheSportsDB:** Your 1.x TheSportsDB key is still under Key, which 2.0 only sends to football-data.org: paste it under Premium key, then clear Key (or put your football-data.org key there). Until then those
  screens say NEEDS A KEY, THESPORTSDB PREMIUM and fetch nothing. Users of football-data.org have nothing to do.

## 1.0.0
- First release. Football: next match, live score, result and the league table around your team.
- Sources: football-data.org (your own free key, top leagues) and TheSportsDB (your own Premium key).
