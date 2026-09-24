# Explicit: make's built-in default CC = cc would win over "CC ?= gcc".
CC = gcc
CFLAGS ?= -std=c11 -Wall -Wextra -Werror -I../main

TEST_BINS = test_button_gesture.out test_url_decode.out

.PHONY: all clean

all: $(TEST_BINS)
	./test_button_gesture.out
	./test_url_decode.out

test_button_gesture.out: test_button_gesture.c ../main/button_gesture.c ../main/button_gesture.h
	$(CC) $(CFLAGS) -o $@ test_button_gesture.c ../main/button_gesture.c

test_url_decode.out: test_url_decode.c ../main/url_decode.c ../main/url_decode.h
	$(CC) $(CFLAGS) -o $@ test_url_decode.c ../main/url_decode.c

clean:
	rm -f $(TEST_BINS)
