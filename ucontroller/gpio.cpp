#include <stdlib.h>
#include <limits.h>
#include <stdio.h>

#include "cmd.h"
#include "gpio.h"

CMD cmd_gpio = {
    name : "gpio",
    init : &init_gpio,
    exec : &exec_gpio,
    help : &help_gpio
};

//List of GPIO pin
const int GPIO_PIN[] = {
    22,  23,  24,  25,
    26,  27,  28,  29,
    30,  31,  32,  33,
    34,  35,  36,  37,
    38,  39,  40,  41,  
    42,  43,  44,  45,  
    46,  47,  48,  49,  
    50,  51,  52,  53
};

int init_gpio() {
    // Initialize gpio
    for (int i = 0; i < sizeof(GPIO_PIN) / sizeof(GPIO_PIN[0]); i++) {
        pinMode(GPIO_PIN[i], OUTPUT);
    }

    return 0;
}

int help_gpio() {
    Serial.println("Read or write the gpio. Valid GPIO number ranges from 22 to 37.");
    Serial.println("To read gpio No.22:");
    Serial.println("  gpio 22");
    Serial.println("To write 1 to gpio No.53:");
    Serial.println("  gpio 53 1");

    return 0;
}

int exec_gpio() {

    /* Convert the provided value to a decimal long */
    long int gpio_pin = atol(args[1]);

    if (gpio_pin == 0) {
        // nothing parsed from the string, handle errors or exit
        Serial.print("Conversion error occurred: ");
        return 1;
    }

    if ((gpio_pin>53 || gpio_pin<22)) {
        // out of range, handle or exit
        Serial.println("The value provided was out of range.");
        return 1;
    }

    if (strcmp(args[2], "0") == 0) {
        digitalWrite(gpio_pin, 0);
    } else if (strcmp(args[2], "1") == 0) {
        digitalWrite(gpio_pin, 1);
    } else if (strcmp(args[2], "") == 0) {
        int val = digitalRead(gpio_pin);
        Serial.println(val);
    } else {
        Serial.println("Invalid command.");
    }

    return 0;
}
