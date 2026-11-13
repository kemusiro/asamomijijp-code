// SPDX-License-Identifier: MIT
#include "transport.h"
#include "pico/i2c_slave.h"
#include "hardware/gpio.h"
static revc_transport transport;
static void drain(i2c_inst_t *bus){while(i2c_get_read_available(bus))revc_transport_byte(&transport,(uint8_t)i2c_read_byte_raw(bus));}
static void callback(i2c_inst_t *bus,i2c_slave_event_t event){
    if(event==I2C_SLAVE_RECEIVE)drain(bus);
    else if(event==I2C_SLAVE_FINISH){
        // SDK2.2.0 can report STOP before RX_FULL in the same IRQ snapshot.
        // Collect the trailing FIFO bytes before committing the transaction.
        drain(bus);revc_transport_finish(&transport);
    }
    else if(event==I2C_SLAVE_REQUEST)i2c_write_byte_raw(bus,revc_transport_read(&transport));
}
void revc_i2c_init(void){
    revc_transport_init(&transport);i2c_init(i2c0,100000);
    gpio_set_function(20,GPIO_FUNC_I2C);gpio_set_function(21,GPIO_FUNC_I2C);
    // Rev C's existing4.7k pullups provide3.3V;no GPIO reassignment or extra pulls.
    i2c_slave_init(i2c0,0x42,callback);
}
int revc_i2c_pop(uint8_t out[REVC_PACKET_MAX]){return revc_transport_pop(&transport,out);}
void revc_i2c_publish(const uint8_t status[REVC_STATUS_SIZE]){revc_transport_publish(&transport,status);}
