// SPDX-License-Identifier: MIT
#include "pico/unique_id.h"
#include "tusb.h"
#include <string.h>
#include <stdint.h>
// Pico SDK's RP2350 CDC test identity;no claim of a custom allocated USB PID.
static tusb_desc_device_t const device={
    .bLength=sizeof(tusb_desc_device_t),.bDescriptorType=TUSB_DESC_DEVICE,.bcdUSB=0x0200,
    .bDeviceClass=TUSB_CLASS_MISC,.bDeviceSubClass=MISC_SUBCLASS_COMMON,.bDeviceProtocol=MISC_PROTOCOL_IAD,
    .bMaxPacketSize0=64,.idVendor=0x2e8a,.idProduct=0x0009,.bcdDevice=0x0501,
    .iManufacturer=1,.iProduct=2,.iSerialNumber=3,.bNumConfigurations=1
};
static uint8_t const configuration[]={
    TUD_CONFIG_DESCRIPTOR(1,4,0,TUD_CONFIG_DESC_LEN+TUD_CDC_DESC_LEN+8+TUD_MIDI_DESC_LEN,0,100),
    TUD_CDC_DESCRIPTOR(0,4,0x81,8,0x02,0x82,64),
    // Group the Audio Control + MIDI Streaming interfaces in this composite.
    8,TUSB_DESC_INTERFACE_ASSOCIATION,2,2,TUSB_CLASS_AUDIO,0,0,5,
    TUD_MIDI_DESCRIPTOR(2,5,0x03,0x83,64)
};
static char serial[PICO_UNIQUE_BOARD_ID_SIZE_BYTES*2+1];
void revc_usb_identity_init(void){pico_get_unique_board_id_string(serial,sizeof(serial));}
uint8_t const *tud_descriptor_device_cb(void){return (uint8_t const *)&device;}
uint8_t const *tud_descriptor_configuration_cb(uint8_t index){(void)index;return configuration;}
uint16_t const *tud_descriptor_string_cb(uint8_t index,uint16_t langid) {
    (void)langid;static uint16_t text[64];
    const char *s;
    if(!index){text[0]=(TUSB_DESC_STRING<<8)|4;text[1]=0x0409;return text;}
    switch(index){case 1:s="Pico SDK prototype";break;case 2:s="YM2203 Rev C C MIDI";break;case 3:s=serial;break;case 4:s="Rev C control";break;case 5:s="YM2203 Rev C MIDI";break;default:return NULL;}
    unsigned n=(unsigned)strlen(s);if(n>63)n=63;
    for(unsigned i=0;i<n;i++)text[i+1]=(uint8_t)s[i];
    text[0]=(uint16_t)((TUSB_DESC_STRING<<8)|(2*n+2));return text;
}
