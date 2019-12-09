#include <string.h>
#include <stdlib.h>
#include <limits.h>
#include <stdio.h>

#include "exit.h"
#include "cmd.h"


CMD cmd_exit = {
    name : "exit",
    init : &init_exit,
    exec : &exec_exit,
    help : &help_exit
};


int init_exit() {
    return 0;
}

int help_exit() {
    Serial.println("This will exit the CLI. To restart the CLI, restart the program.");
    return 0;
}

int exec_exit() {
    Serial.println("Exiting CLI.");

    while (1);
}
