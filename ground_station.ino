/**
 * @file satrllite.ino
 * @author Ana-Maria Bogdanova (ana.maria.bogdanova@gmail.com)
 * @brief 
 * @version 0.1
 * @date 2025-06-19
 * 
 * @copyright Copyright (c) 2025
 * 
 */

/** INCLUDES */
#include <SoftwareSerial.h>
#include <RH_RF95.h>

/** DEFINES */
#define LED 13
#define TIMEOUT (3000)

/** VARIABLES */
SoftwareSerial ss(3, 4);
RH_RF95<SoftwareSerial> rf95(ss);

String command;
String input;
unsigned char data[4];

unsigned long now = 0;
unsigned long last_us = 0;

/** SETUP */
void setup() 
{
  //Serial init
  Serial.begin(115200);
  Serial.println("Ground station communication test.");

  pinMode(LED, OUTPUT);  //LED init

  //LORA communication init
  if(!rf95.init())
  {
    Serial.println("RF initialisation failed!");
  }
  rf95.setFrequency(434.0);
}

/** MAIN CODE */
void loop()
{
  //Serial.print("Input command (batt/rssi/uptime/power=*value*/coord/cartesian/acc/ang_vel/magn_field/adcs/temp_C/temp_K): \n");

  now = micros();
  float dt = float(now - last_us) * 1e-3f; // convert us to milliseconds;
  last_us = now;
  //Serial.println(dt);

  if(Serial.available())
  {
    input = Serial.readStringUntil('\n');
  }
  //delay(2500);
  command = input;

  
  if(command.equals("1"))
  {
    strcpy((char*)data, "1");
    rf95.send(data, sizeof(data));
    rf95.waitPacketSent();
    //Serial.println("Get battery command sent.");
  }
  else if(command.equals("2"))
  {
    strcpy((char*)data, "2");
    rf95.send(data, sizeof(data));
    rf95.waitPacketSent();
    //.println("Get RSSI command sent.");
  }
  else if(command.equals("3"))
  {
    strcpy((char*)data, "3");
    rf95.send(data, sizeof(data));
    rf95.waitPacketSent();
    //Serial.println("Get uptime command sent.");
  }
  else if(command.equals("4"))
  {
    strcpy((char*)data, "4");
    rf95.send(data, sizeof(data));
    rf95.waitPacketSent();
    //Serial.println("Change rf power command sent.");
  }
  else if(command.equals("5"))
  {
    strcpy((char*)data, "5");
    rf95.send(data, sizeof(data));
    rf95.waitPacketSent();
    //Serial.println("Get coordinates command sent.");
  }
  else if(command.equals("6"))
  {
    strcpy((char*)data, "6");
    rf95.send(data, sizeof(data));
    rf95.waitPacketSent();
    //Serial.println("Get Cartesian coordinates command sent.");
  }
  else if(command.equals("7"))
  {
    strcpy((char*)data, "7");
    rf95.send(data, sizeof(data));
    rf95.waitPacketSent();
    //Serial.println("Get acceleration command sent.");
  }
  else if(command.equals("8"))
  {
    strcpy((char*)data, "8");
    rf95.send(data, sizeof(data));
    rf95.waitPacketSent();
    //Serial.println("Get velocity command sent.");
  }
  else if(command.equals("9"))
  {
    strcpy((char*)data, "9");
    rf95.send(data, sizeof(data));
    rf95.waitPacketSent();
    //Serial.println("Get magnetic field command sent.");
  }
  else if(command.equals("10"))
  {
    strcpy((char*)data, "10");
    rf95.send(data, sizeof(data));
    rf95.waitPacketSent();
    //Serial.println("Get ASDCS data (pitch, roll, heading) command sent.");
  }
  else if(command.equals("11"))
  {
    strcpy((char*)data, "11");
    rf95.send(data, sizeof(data));
    rf95.waitPacketSent();
    //Serial.println("Get temperature in C command sent.");
  }
  else if(command.equals("12"))
  {
    strcpy((char*)data, "12");
    rf95.send(data, sizeof(data));
    rf95.waitPacketSent();
    //Serial.println("Get temperature in K command sent.");
  }
  else
  {
    //Serial.println("Invalid command.");
  }

  if(rf95.waitAvailableTimeout(TIMEOUT))
  {
    uint8_t buf[RH_RF95_MAX_MESSAGE_LEN];
    uint8_t len = sizeof(buf);
    if(rf95.recv(buf, &len))
    {
      Serial.println((char*)buf);
    }
    else
    {
      Serial.println("Data lost.");
    }
  }
  else
  {
    Serial.println("No reply from the satellite.");
  }
  //delay(1000);
}
