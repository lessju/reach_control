#include <stdlib.h>
#include <limits.h>
#include <stdio.h>

#include "cmd.h"
#include "pwm.h"

CMD cmd_pwm = {
    name : "pwm",
    init : &init_pwm,
    exec : &exec_pwm,
    help : &help_pwm
};

//List of PWM pin
const int PWM_PIN[] = {
    2,  3,  
    4,  5,
    6,  7
};

int init_pwm() {

    int npwm = sizeof(PWM_PIN) / sizeof(PWM_PIN[0]);

    // Initialize pwm
    for (int i = 0; i < npwm; i++) {
        pinMode(PWM_PIN[i], OUTPUT);
    }

    return 0;
}

int help_pwm() {
    Serial.println("generate pwm, default frequency at 1000Hz.");
    Serial.println("Valid PWM pin number ranges from 2 to 7.");
    Serial.println("Valid value of duty cycle ranges from 0 to 255.");
    Serial.println("To set pwm No.2 to 50\% duty cycle:");
    Serial.println("  pwm 2 127");
    Serial.println("To pwm No.7 to 100\% duty cycle:");
    Serial.println("  pwm 7 255");

    return 0;
}

int exec_pwm() {

    /* Convert the provided value to a decimal long */
    int pwm_pin = atoi(args[1]);

    if (pwm_pin == 0) {
        // nothing parsed from the string, handle errors or exit
        Serial.print("Conversion error occurred: ");
        Serial.println(args[1]);
        return 1;
    }

    if ((pwm_pin>7 || pwm_pin<2)) {
        // out of range, handle or exit
        Serial.print("The value provided was out of range: ");
        Serial.println(args[1]);
        return 1;
    }

    if (strcmp(args[2], "") == 0) {
        int val = analogRead(pwm_pin);
        Serial.println(val);
        return 0;
    } else {
        int pwm_dty = atoi(args[2]);

        if (pwm_dty == 0 and strcmp(args[2],"0") != 0) {
            Serial.print("Conversion error occurred: ");
            return 1;
        } 

        if ((pwm_pin>255 || pwm_pin<0)) {
            // out of range, handle or exit
            Serial.println("The value provided was out of range.");
            return 1;
        }

        analogWrite(pwm_pin, pwm_dty);
    }

    return 0;
}
