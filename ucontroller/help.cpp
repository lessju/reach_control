#include <string.h>
#include <stdlib.h>
#include <limits.h>
#include <stdio.h>

#include "cmd.h"
#include "help.h"

CMD cmd_help = {
    name : "help",
    init : &init_help,
    exec : &exec_help,
    help : &help_help
};

int help_help() {
    Serial.println("The following commands are available:");

    for (int i = 0; i < ncmd; i++) {
        Serial.print("    ");
        Serial.println(cmds[i].name);
    }
    Serial.println("");
    Serial.println("You can for instance type \"help led\" for more info on the LED command.");

    return 0;
}

int exec_help() {

    if (args[1] == NULL) {
        help_help();
        return 0;
    }

    CMD *pcmd = find_cmd(args[1]);

    if (pcmd!=NULL) {
        return pcmd->help();
    } else {
        help_help();
        return 0;
    }

}

int init_help() {
    return 0;
}
