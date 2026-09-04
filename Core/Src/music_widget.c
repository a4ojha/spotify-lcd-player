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

uint8_t block_icon[8] = {
    0b11111,
    0b11111,
    0b11111,
    0b11111,
    0b11111,
    0b11111,
    0b11111,
    0b11111
};

static char g_title[]  = "Kiss of Life";
static char g_artist[] = "Sade";

void widget_init(void)
{
    lcd_init();
    lcd_clear();

    lcd_create_char(0, prev_icon);
    lcd_create_char(1, pause_icon);
    lcd_create_char(2, next_icon);
    lcd_create_char(3, block_icon);
    
    // Progress bar
    lcd_put_cur(2, 2);
    lcd_send_string("[");
    for (int i = 0; i < 3; i++) {
        lcd_send_data(3);
    }
    lcd_send_string("-----------]");
    
    // Media control icons
    lcd_put_cur(3, 5); lcd_send_data(0);  // prev
    lcd_put_cur(3, 9); lcd_send_data(1);  // pause
    lcd_put_cur(3, 13); lcd_send_data(2);  // next
}

void display_line(char *str, int row, int *offset)
{
    char out[21];
    int len = strlen(str);

    if (len <= 20) {
        int start = (20 - len) / 2;
        for (int i = 0; i < 20; i++) out[i] = ' ';
        for (int i = 0; i < len; i++) out[start + i] = str[i];
        out[20] = '\0';
        *offset = 0;
    } 
    // scrolling line
    else {
        for (int i = 0; i < 20; i++) {
            out[i] = str[*offset + i];
        }
        out[20] = '\0';

        // increment offset for next tick; reset when last char hits right edge
        (*offset)++;
        if (*offset > len - 20) *offset = 0;
    }

    lcd_put_cur(row, 0);
    lcd_send_string(out);
}

void widget_render_frame(void)
{
    static int title_offset = 0;
    static int artist_offset = 0;
    display_line(g_title,  0, &title_offset);
    display_line(g_artist, 1, &artist_offset);
}
