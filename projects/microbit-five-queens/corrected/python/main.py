import random
from microbit import *

n = 5

du = [0.0] * (n * n)
u = [0.0] * (n * n)
v = [0] * (n * n)

A = 1.0
B = 1.0
C = 1.0

def initialize(u, v, n):
    for i in range(n * n):
        u[i] = random.uniform(-1.0, 1.0)
        if u[i] > 0.0:
            v[i] = 1
        else:
            v[i] = 0

def judge(v, du, n):
    number_of_queens = 0;
    for i in range(n * n):
        if v[i] == 1:
            if du[i] == 0.0:
                number_of_queens += 1
    return number_of_queens == n

def print_network(v, n):
    result = ""
    for i in range(n):
        for j in range(n):
            result = result + str(v[i * n + j] * 9)
        result = result + ":"
    image = Image(result)
    display.show(image)

display.show("Q")
while True:
    if button_a.is_pressed():
        break

while True:
    trial = 1;
    found = False;
    while True:
        initialize(u, v, n)
        for epoch in range(1, 101):
            for i in range(n):
                for j in range(n):
                    s = 0.0
                    du[i * n + j] = 0.0

                    for k in range(n):
                        s += v[i * n + k]
                    du[i * n + j] += -A * (s - 1)

                    s = 0.0
                    for k in range(n):
                        s += v[k * n + j]
                    du[i * n + j] += -A * (s - 1)

                    s = 0.0
                    for k in range(-n + 1, n):
                        if k != 0 and i - k >= 0 and i - k <= n - 1 and j - k >= 0 and j - k <= n - 1:
                            s += v[(i - k) * n + j - k]
                    du[i * n + j] += -B * s

                    s = 0.0
                    for k in range(-n + 1, n):
                        if k != 0 and i - k >= 0 and i - k <= n - 1 and j + k >= 0 and j + k <= n - 1:
                            s += v[(i - k) * n + j + k]
                    du[i * n + j] += -B * s

                    c = False
                    for k in range(n):
                        if v[i * n + k] == 1:
                            c = True
                            break
                    if c == False:
                        du[i * n + j] += C

                    c = False
                    for k in range(n):
                        if v[k * n + j] == 1:
                            c = True
                            break
                    if c == False:
                        du[i * n + j] += C

            for i in range(n):
                for j in range(n):
                    u[i * n + j] += du[i * n + j]
                    v[i * n + j] = 1 if u[i * n + j] > 0 else 0
            print_network(v, n)
            if judge(v, du, n):
                found = True
                break;
        if found == True:
            break
        trial += 1

    total = (trial - 1) * 100 + epoch

    while True:
        if button_a.is_pressed():
            break
        elif button_b.is_pressed():
            display.scroll(str(total))
            print_network(v, n)
