#include <stdlib.h>
#include <limits.h>
#include <stdio.h>

#include "cmd.h"
#include "led.h"


CMD cmd_led = {
    name : "led",
    init : &init_led,
    exec : &exec_led,
    help : &help_led
};

int LEDpin = 13;
int blink_cycles = 10;      //How many times the LED will blink

//List of LED sub command names
const char *led_args[] = {
    "on",
    "off",
    "blink"
};

int init_led() {
    // Initialize led
    pinMode(LEDpin, OUTPUT);
    return 0;
}

int help_led() {
    Serial.print("Control the on-board LED, either on, off or blinking ");
    Serial.print(blink_cycles);
    Serial.println(" times:");
    Serial.println("  led on");
    Serial.println("  led off");
    Serial.println("  led blink hz");
    Serial.println("    where \"hz\" is the blink frequency in Hz.");
    return 0;
}

int exec_led() {
    if (strcmp(args[1], led_args[0]) == 0) {
        Serial.println("Turning on the LED.");
        digitalWrite(LEDpin, HIGH);
    }
    else if (strcmp(args[1], led_args[1]) == 0) {
        Serial.println("Turning off the LED.");
        digitalWrite(LEDpin, LOW);
    }
    else if (strcmp(args[1], led_args[2]) == 0) {
        if (atoi(args[2]) > 0) {
            Serial.print("Blinking the LED ");
            Serial.print(blink_cycles);
            Serial.print(" times at ");
            Serial.print(args[2]);
            Serial.println(" Hz.");

            int delay_ms = (int)round(1000.0 / atoi(args[2]) / 2);

            for (int i = 0; i < blink_cycles; i++) {
                digitalWrite(LEDpin, HIGH);
                delay(delay_ms);
                digitalWrite(LEDpin, LOW);
                delay(delay_ms);
            }
        }
        else {
            Serial.println("Invalid frequency.");
        }
    }
    else {
        Serial.println("Invalid command. Type \"help led\" to see how to use the LED command.");
    }

    return 0;
}
