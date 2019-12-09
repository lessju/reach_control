#ifndef PWM_H
#define PWM_H

#include "cmd.h"

extern CMD cmd_pwm;

int init_pwm();
int help_pwm();
int exec_pwm();

#endif
