#include "music_widget.h"
#include "i2c-lcd.h"
#include <string.h>
#include <stdio.h>

uint8_t prev_icon[8] = {   
    0b10001,
    0b10011,
    0b10111,
    0b11111,
    0b10111,
    0b10011,
    0b10001,
    0b00000
};

uint8_t pause_icon[8] = {  
    0b11011,
    0b11011,
    0b11011,
    0b11011,
    0b11011,
    0b11011,
    0b11011,
    0b00000
};

uint8_t next_icon[8] = {
    0b10001,
    0b11001,
    0b11101,
    0b11111,
    0b11101,
    0b11001,
    0b10001,
    0b00000
};

void widget_init(void)
{
    lcd_init();
    lcd_clear();

    // lcd_create_char(0, prev_icon);
    // lcd_create_char(1, pause_icon);
    // lcd_create_char(2, next_icon);

    char title[] = "nice shoes";
    char artist[] = "Steve Lacy";

    // lcd_put_cur(0, get_start_position(title));
    // lcd_send_string(title);
    // lcd_put_cur(1, get_start_position(artist));
    // lcd_send_string(artist);

    lcd_put_cur(2, 5);
    lcd_send_string("A");  // prev
    // lcd_put_cur(2, 9);
    // lcd_send_string("B");  // pause
    // lcd_put_cur(2, 13);
    // lcd_send_string("C");  // next
}

int get_start_position(char *str)
{
    int len = strlen(str);
    return (20 - len) / 2;
}

