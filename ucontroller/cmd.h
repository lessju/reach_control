#ifndef CMD_H
#define CMD_H

#include <Arduino.h>

#define LINE_BUF_SIZE 128   //Maximum input string length
#define ARG_BUF_SIZE 64     //Maximum argument string length
#define MAX_NUM_ARGS 8      //Maximum number of arguments

extern char args[MAX_NUM_ARGS][ARG_BUF_SIZE];

extern int ncmd;

typedef struct PString {
    char *name;
    int (*init)();
    int (*exec)();
    int (*help)();
} CMD;

extern CMD cmds[];

CMD* find_cmd(char *);

#endif
