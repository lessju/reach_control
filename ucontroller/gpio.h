#ifndef GPIO_H
#define GPIO_H

#include "cmd.h"

extern CMD cmd_gpio;

int init_gpio();
int help_gpio();
int exec_gpio();

#endif
