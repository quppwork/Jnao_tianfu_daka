# -*- coding: utf-8 -*-
from pathlib import Path

p = Path(r"d:/daka/Jnao_tianfu_daka/vue_fronted/src/static/dayu/html/answer.html")
t = p.read_text(encoding="utf-8")

repls = [
    (
        "math:{ava:'/static/dayu/assets/parent-team.jpg',gif:'/static/dayu/assets/gif/mentor-math.gif'",
        "math:{ava:'/static/dayu/assets/avatar-math.jpg',gif:'/static/dayu/assets/gif/mentor-math.gif'",
    ),
    (
        "chinese:{ava:'/static/dayu/assets/parent-team.jpg',gif:'/static/dayu/assets/gif/mentor-chinese.gif'",
        "chinese:{ava:'/static/dayu/assets/avatar-chinese.jpg',gif:'/static/dayu/assets/gif/mentor-chinese.gif'",
    ),
    (
        "english:{ava:'/static/dayu/assets/parent-team.jpg',gif:'/static/dayu/assets/gif/mentor-english.gif'",
        "english:{ava:'/static/dayu/assets/avatar-english.jpg',gif:'/static/dayu/assets/gif/mentor-english.gif'",
    ),
    (
        "science:{ava:'/static/dayu/assets/parent-team.jpg',gif:'/static/dayu/assets/gif/mentor-science.gif'",
        "science:{ava:'/static/dayu/assets/avatar-dayu.jpg',gif:'/static/dayu/assets/gif/mentor-science.gif'",
    ),
    (
        "mind:{ava:'/static/dayu/assets/parent-team.jpg',gif:'/static/dayu/assets/gif/mentor-mind.gif'",
        "mind:{ava:'/static/dayu/assets/avatar-mind.jpg',gif:'/static/dayu/assets/gif/mentor-mind.gif'",
    ),
    (
        "ava:'/static/dayu/assets/parent-team.jpg',tb:'思'",
        "ava:'/static/dayu/assets/avatar-dayu.jpg',tb:'思'",
    ),
]

for old, new in repls:
    if old not in t:
        print("MISS:", old[:70])
    else:
        t = t.replace(old, new)
        print("OK:", new[new.find("ava:") : new.find("ava:") + 55])

p.write_text(t, encoding="utf-8", newline="\n")
print("remaining parent-team:", t.count("parent-team.jpg"))
