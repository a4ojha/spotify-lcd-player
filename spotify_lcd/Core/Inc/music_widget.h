void widget_init(void);
void widget_render_scroll(void);
void widget_handle_message(char *msg);
static void display_line(char *str, int row, int *offset);
static void update_song(char *title, char *artist);
static void update_progress_bar(int progress);
static void update_play_pause_icon(int is_playing);