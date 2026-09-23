# Explicit: make's built-in default CC = cc would win over "CC ?= gcc".
CC = gcc
CFLAGS ?= -std=c11 -Wall -Wextra -Werror -I../main

TEST_BIN = test_button_gesture.out

.PHONY: all clean

all: $(TEST_BIN)
	./$(TEST_BIN)

$(TEST_BIN): test_button_gesture.c ../main/button_gesture.c ../main/button_gesture.h
	$(CC) $(CFLAGS) -o $@ test_button_gesture.c ../main/button_gesture.c

clean:
	rm -f $(TEST_BIN)
