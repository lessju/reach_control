#include <string.h>
#include <stdlib.h>
#include <limits.h>
#include <stdio.h>

#include "cmd.h"
#include "led.h"
#include "gpio.h"
#include "help.h"
#include "exit.h"
#include "pwm.h"
#include "temp.h"

#define LINE_BUF_SIZE 128   //Maximum input string length
#define ARG_BUF_SIZE 64     //Maximum argument string length
#define MAX_NUM_ARGS 8      //Maximum number of arguments

char line[LINE_BUF_SIZE];
char args[MAX_NUM_ARGS][ARG_BUF_SIZE];

CMD cmds[] = {
    cmd_led,
    cmd_gpio,
    cmd_pwm,
    cmd_temp,
    cmd_help,
    cmd_exit
};

bool error_flag = false;

int ncmd = sizeof(cmds) / sizeof(CMD);

CMD* find_cmd(char *s){

    CMD *p = NULL;

    for (int i=0; i<ncmd; i++) {
        if (strcmp(s,cmds[i].name) == 0) {
            p = &cmds[i];
            break;
        } else {
            continue;
        }
    }

    return p;
}

void setup() {
    Serial.begin(115200);

    for (int i=0; i<ncmd; i++) {
        cmds[i].init();
    }

    cli_init();
}

void loop() {
    my_cli();
}

void cli_init() {
    Serial.println("Welcome to this simple Arduino command line interface (CLI).");
    Serial.println("Type \"help\" to see a list of commands.");
}

void my_cli() {
//    Serial.print("> ");

    read_line();
    if (!error_flag) {
        parse_line();
    }
    if (!error_flag) {
        execute();
    }

    memset(line, 0, LINE_BUF_SIZE);
    memset(args, 0, sizeof(args[0][0]) * MAX_NUM_ARGS * ARG_BUF_SIZE);

    error_flag = false;
}

void read_line() {
    String line_string;

    while (!Serial.available());

    if (Serial.available()) {
        line_string = Serial.readStringUntil('\n');
        if (line_string.length() < LINE_BUF_SIZE) {
            line_string.toCharArray(line, LINE_BUF_SIZE);
//            Serial.println(line_string);
        }
        else {
            Serial.println("Input string too long.");
            error_flag = true;
        }
    }
}

void parse_line() {
    char *argument;
    int counter = 0;

    argument = strtok(line, " ");

    while ((argument != NULL)) {
        if (counter < MAX_NUM_ARGS) {
            if (strlen(argument) < ARG_BUF_SIZE) {
                strcpy(args[counter], argument);
                argument = strtok(NULL, " ");
                counter++;
            }
            else {
                Serial.println("Input string too long.");
                error_flag = true;
                break;
            }
        }
        else {
            break;
        }
    }
}

int execute() {

    CMD *pcmd = find_cmd(args[0]);

    if (pcmd!=NULL) {
        return pcmd->exec();
    } else {
        Serial.println("Invalid command. Type \"help\" for more.");
        return 0;
    }

}
