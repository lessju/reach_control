#include <stdlib.h>
#include <limits.h>
#include <stdio.h>

#include "cmd.h"
#include "temp.h"
//#include "i2c.h"
//#include "i2c_SI7021.h"
#include "Adafruit_Si7021.h"

CMD cmd_temp = {
    name : "temp",
    init : &init_temp,
    exec : &exec_temp,
    help : &help_temp
};

//SI7021 si7021;
Adafruit_Si7021 sensor = Adafruit_Si7021();

static float h, t;

int init_temp() {

//    if (si7021.initialize()) {
//        //Serial.println("Sensor found!");
//        return 0;
//    } else {
//        Serial.println("SI7021 Sensor missing");
//        return 1;
//    }

    if (!sensor.begin()) {
        Serial.println("Did not find Si7021 sensor!");
    }
}

int help_temp() {
    Serial.println("Temperature sensor Si7021. Examples:");
    Serial.println("Read temperature in degree celsius:");
    Serial.println("  temp temp");
    Serial.println("Read humidity");
    Serial.println("  temp humi");

    return 0;
}

int exec_temp() {

    if (strcmp(args[1], "temp") == 0) {

//        si7021.getTemperature(t);
//        si7021.triggerMeasurement();
//        Serial.println(t);
        Serial.println(sensor.readHumidity());
        return 0;

    } else if (strcmp(args[1], "humi") == 0) {

//        si7021.getHumidity(h);
//        si7021.triggerMeasurement();
//        Serial.println(h);
        Serial.println(sensor.readTemperature());
        return 0;

    } else {
        Serial.print("Invalid temp command: ");
            Serial.println(args[1]);
            return 1;
    }
}
