#include "music_widget.h"
#include "i2c-lcd.h"
#include <string.h>
#include <stdio.h>
#include <stdlib.h>


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

uint8_t play_icon[8] = {   
    0b10000,
    0b11000,
    0b11100,
    0b11110,
    0b11100,
    0b11000,
    0b10000,
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

int TOTAL_PROG_BAR_CELLS = 14;

static char g_title[64]  = "";
static char g_artist[64] = "";
static int title_scroll_offset = 0;
static int artist_scroll_offset = 0;

void widget_init(void) {
    lcd_init();
    lcd_clear();
    
    lcd_create_char(0, prev_icon);
    lcd_create_char(1, pause_icon);
    lcd_create_char(2, play_icon);
    lcd_create_char(3, next_icon);
    lcd_create_char(4, block_icon);
    
    // Progress bar
    lcd_put_cur(2, 2);
    lcd_send_string("[--------------]");
    
    // Media control icons
    lcd_put_cur(3, 5); lcd_send_data(0);  // prev
    lcd_put_cur(3, 9); lcd_send_data(1);  // pause
    lcd_put_cur(3, 13); lcd_send_data(3);  // next
}


void widget_handle_message(char *msg) {
    char *title = strtok(msg, "|");
    char *artist = strtok(NULL, "|");
    char *progress_str = strtok(NULL, "|");
    char *is_playing_str = strtok(NULL, "|");

    if (!title || !artist || !progress_str || !is_playing_str) {
        return;
    }
    
    int progress = atoi(progress_str);
    int is_playing = atoi(is_playing_str);

    // DEBUG /////////
    printf("Received message:\r\n");
    printf("Title: %s\r\n", title);
    printf("Artist: %s\r\n", artist);
    printf("Progress: %d\r\n", progress);
    printf("Is Playing: %d\r\n", is_playing);
    /////////////////

    update_song(title, artist);
    update_progress_bar(progress);
    update_play_pause_icon(is_playing);
}

void widget_render_scroll(void)
{
    display_line(g_title,  0, &title_scroll_offset);
    display_line(g_artist, 1, &artist_scroll_offset);
}

static void display_line(char *str, int row, int *offset)
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

static void update_song(char *title, char *artist) {
    if (strcmp(title, g_title) != 0 || strcmp(artist, g_artist) != 0) {
        strncpy(g_title, title, sizeof(g_title) - 1);
        g_title[sizeof(g_title) - 1] = '\0';
        strncpy(g_artist, artist, sizeof(g_artist) - 1);
        g_artist[sizeof(g_artist) - 1] = '\0';

        // new song, reset scroll so titles start from the beginning
        title_scroll_offset = 0;
        artist_scroll_offset = 0;
    }
}

static void update_progress_bar(int progress) {
    static int last_filled = -1;
    int filled_cells = (TOTAL_PROG_BAR_CELLS * progress) / 100;
    if (filled_cells == last_filled) return;
    last_filled = filled_cells;

    // redraw the bar
    // lcd_put_cur(2, 2) is the '[', then filled_cells, then the ']', so we need to fill in the '-'s in between
    lcd_put_cur(2, 3);
    for (int i = 0; i < filled_cells; i++) {
        lcd_send_data(4);
    }
    for (int i = filled_cells; i < TOTAL_PROG_BAR_CELLS; i++) {
        lcd_send_string("-");
    }
}

static void update_play_pause_icon(int is_playing) {
    static int last_state = -1;
    if (is_playing == last_state) return;
    last_state = is_playing;
    lcd_put_cur(3, 9);
    lcd_send_data(is_playing ? 1 : 2);  // pause or play icon
}