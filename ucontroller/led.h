#ifndef LED_H
#define LED_H

#include "cmd.h"

extern CMD cmd_led;

int init_led();
int help_led();
int exec_led();

#endif
