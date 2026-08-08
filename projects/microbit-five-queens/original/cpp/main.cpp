#include "MicroBit.h"

using namespace std;

MicroBit uBit;
MicroBitButton buttonA(MICROBIT_PIN_BUTTON_A, MICROBIT_ID_BUTTON_A);
MicroBitButton buttonB(MICROBIT_PIN_BUTTON_B, MICROBIT_ID_BUTTON_B);
static int n = 5;

static float A = 1.0;
static float B = 1.0;
static float C = 1.0;

static int trial = 0;
static int epoch = 0;

static MicroBitImage img(5, 5);

void error(const char* format, ...) {}

float drand() {
    return ((float)rand() / RAND_MAX) * 2.0 - 1.0;
}

void initialize(float *u, int *v, int n) {
    for (int i = 0; i < n; i++) {
        for (int j = 0; j < n; j++) {
            u[i * n + j] = drand();
            v[i * n + j] = (u[i * n + j] > 0.0) ? 1 : 0;
        }
    }
}

bool judge(int *v, float *du, int n) {
    int number_of_queens = 0;
    for (int i = 0; i < n; i++) {
        for (int j = 0; j < n; j++) {
            if (v[i * n + j] == 1 && du[i * n + j] == 0.0) {
                number_of_queens++;
            }
        }
    }
    return number_of_queens == n;
}

void print_network(int *v, int n) {
    for (int i = 0; i < n; i++) {
        for (int j = 0; j < n; j++) {
            img.setPixelValue(i, j, v[i * n + j] * 255);
        }
    }
    uBit.display.print(img);
}

int main() {
    uBit.init();
    
    uBit.display.print("Q");
    while (!buttonA.isPressed()) {
        drand();
    }
    
    float du[n * n];
    float u[n * n];
    int v[n * n];

    while (true) {
        trial = 1;
        epoch = 1;
        bool found = false;
    
        while (true) {
            int i, j, k;
            float s;
            bool c;
            initialize(u, v, n);
            for (epoch = 1; epoch <= 100; epoch++) {
                for (i = 0; i < n; i++) {
                    for (j = 0; j < n; j++) {
                        s = 0.0;
                        du[i * n + j] = 0.0;
                        for (k = 0; k < n; k++) {
                            s += v[i * n + k];
                        }
                        du[i * n + j] += -A * (s - 1);
    
                        s = 0.0;
                        for (k = 0; k < n; k++) {
                             s += v[k * n + j];
                        }
                        du[i * n + j] += -A * (s - 1);
    
                        s = 0.0;
                        for (k = -n + 1; k < n; k++) {
                            if (k != 0 && i - k >= 0 && i - k <= n - 1 && j - k >= 0 && j - k <= n - 1) {
                                s += v[(i - k) * n + j - k];
                            }
                        }
                        du[i * n + j] += -B * s;
    
                        s = 0.0;
                        for (k = -n + 1; k < n; k++) {
                            if (k != 0 && i - k >= 0 && i - k <= n - 1 && j + k >= 0 && j + k <= n - 1) {
                                s += v[(i - k) * n + j + k];
                            }
    
                        }
                        du[i * n + j] += -B * s;
    
                        c = false;
                        for (int k = 0; k < n; k++) {
                            if (v[i * n + k] == 1) {
                                c = true;
                                break;
                            }
                        }
                        if (c == false) {
                            du[i * n + j] += C;
                        }
                        c = false;
                        for (int k = 0; k < n; k++) {
                            if (v[k * n + j] == 1) {
                                c = true;
                                break;
                            }
                        }
                        if (c == false) {
                            du[i * n + j] += C;
                        }
                    }
                }
                for (int i = 0; i < n; i++) {
                    for (int j = 0; j < n; j++) {
                        u[i * n + j] += du[i * n + j];
                        v[i * n + j] = (u[i * n + j] > 0) ? 1 : 0;
                    }
                }
                print_network(v, n);
                if (judge(v, du, n)) {
                    found = true;
                    break;
                }
            }
            if (found) {
                break;
            }
            trial++;
        }
        
        int total = (trial - 1) * 100 + epoch;
        
        while (true) {
            if (buttonA.isPressed()) {
                break;
            }
            else if (buttonB.isPressed()) {
                uBit.display.scroll(total);
                print_network(v, n);
            }
            drand();
        }
    }
    
    return 0;
}
