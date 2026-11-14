CC ?= gcc
CFLAGS ?= -Wall -Wextra -Werror -std=c99 -Isrc

.PHONY: all build test clean

all: build

build: strbuf.o
	$(CC) $(CFLAGS) -o test_strbuf strbuf.o tests/test_strbuf.c

strbuf.o: src/strbuf.c src/strbuf.h
	$(CC) $(CFLAGS) -c src/strbuf.c -o strbuf.o

test: build
	./test_strbuf

clean:
	rm -f strbuf.o test_strbuf
