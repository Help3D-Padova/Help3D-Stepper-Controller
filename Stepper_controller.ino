// --------------------------------------
// CONFIGURAZIONE HARDWARE - HELP3D STEPPER CONTROLLER - www.help3d.it
// Canale YouTube: https://www.youtube.com/@help3d
// --------------------------------------
const int STEP_PIN = 9; // cambiare questi pin a piacere
const int DIR_PIN  = 8;
const int ENA_PIN  = 10;

const int fullStepsPerRev = 200;  // step interi del motore (NEMA standard)

// Parametri motore
int microstep = 16;        // valore iniziale (poi aggiornato da GUI)
long stepsPerRev;

// RPM
float targetRPM = 0;
float currentRPM = 0;
float minRPM = 5;
float maxRPM = 0;
float lastSetRPM = 0;
bool zeroMessageShown = false;

// Profili accelerazione (RPM/s)
float accelProfiles[3] = {50.0, 150.0, 400.0};
int accelProfile = 1;

// Stato
bool motorRunning = false;
bool directionCW  = true;

// Soft-reverse
bool directionChangePending = false;
bool pendingDirectionCW = true;
float savedTargetRPM = 0;

// Timer rampa
unsigned long lastRampUpdateMillis = 0;

// Timer step
unsigned long lastStepMicros = 0;
float stepIntervalMicros = 0;

// Limite tecnico sketch (step/s)
const float STEP_S_LIMIT = 5000.0;

// Telemetria
unsigned long lastTelemetryMillis = 0;


// --------------------------------------
// PROTOTIPI
// --------------------------------------
void handleSerial();
void handleCommand(String cmd);
void requestDirectionChange(bool newCW);
void handleSoftReverse();
void updateSoftStart();
void updateStepInterval();
void stepMotorIfNeeded();
void setMicrostepValue(int m);
void recalcMaxRPM();
void sendTelemetry();


// --------------------------------------
// GRAFICA COMANDI
// --------------------------------------
void printCommands() {
  Serial.println("===========================================");
  Serial.println("                  COMANDI");
  Serial.println("===========================================");
  Serial.println("  START / STOP");
  Serial.println("  SET_SPEED:<RPM>");
  Serial.println("  DIR:CW / DIR:CCW");
  Serial.println("  SET_PROFILE:1/2/3");
  Serial.println("  MICROSTEP:<1|2|4|8|16|32|64>");
  Serial.println("-------------------------------------------");
  Serial.println("  (Compatibilità tasti: W/S/1/2/3)");
  Serial.println("===========================================");
  Serial.println();
}


// --------------------------------------
// SETUP
// --------------------------------------
void setup() {
  Serial.begin(115200);
  delay(300);

  pinMode(STEP_PIN, OUTPUT);
  pinMode(DIR_PIN, OUTPUT);
  pinMode(ENA_PIN, OUTPUT);
  digitalWrite(ENA_PIN, LOW);

  directionCW = true;
  digitalWrite(DIR_PIN, HIGH);

  // Banner HELP3D
  Serial.println("+--------------------------------------------------+");
  Serial.println("|                 HELP3D Stepper                  |");
  Serial.println("|           www.youtube.com/@help3d               |");
  Serial.println("|               www.help3d.it                     |");
  Serial.println("+--------------------------------------------------+");
  Serial.println();

  // Microstepping di default (GUI lo aggiornerà)
  setMicrostepValue(microstep);

  printCommands();

  updateStepInterval();
  lastRampUpdateMillis = millis();
}


// --------------------------------------
// LOOP
// --------------------------------------
void loop() {
  handleSerial();
  handleSoftReverse();
  updateSoftStart();

  if (currentRPM > 0) stepMotorIfNeeded();

  sendTelemetry();  // 🔥 telemetria realtime
}


// --------------------------------------
// SERIAL INPUT
// --------------------------------------
void handleSerial() {
  if (!Serial.available()) return;

  String cmd = Serial.readStringUntil('\n');
  cmd.trim();
  if (cmd.length() == 0) return;

  handleCommand(cmd);
}


// --------------------------------------
// PARSING COMANDI
// --------------------------------------
void handleCommand(String cmd) {

  // START
  if (cmd == "W" || cmd == "w" || cmd == "START") {
    motorRunning = true;
    if (targetRPM == 0 && lastSetRPM > 0) targetRPM = lastSetRPM;
    Serial.print("Motore ON | Target RPM: ");
    Serial.println(targetRPM);
    zeroMessageShown = false;
    return;
  }

  // STOP
  if (cmd == "S" || cmd == "s" || cmd == "STOP") {
    motorRunning = false;
    targetRPM = 0;
    Serial.println("Motore OFF | Soft-stop attivo");
    zeroMessageShown = false;
    return;
  }

  // PROFILI ACCELERAZIONE
  if (cmd == "1" || cmd == "SET_PROFILE:1") {
    accelProfile = 0;
    Serial.println("Profilo accelerazione: 1 (soft)");
    return;
  }

  if (cmd == "2" || cmd == "SET_PROFILE:2") {
    accelProfile = 1;
    Serial.println("Profilo accelerazione: 2 (medio)");
    return;
  }

  if (cmd == "3" || cmd == "SET_PROFILE:3") {
    accelProfile = 2;
    Serial.println("Profilo accelerazione: 3 (aggressivo)");
    return;
  }

  // VELOCITÀ
  if (cmd.startsWith("SET_SPEED:")) {
    float rpm = cmd.substring(10).toFloat();

    if (rpm < 0) rpm = 0;
    if (rpm > maxRPM) {
      rpm = maxRPM;
      Serial.print("⚠ Limite RPM: ");
      Serial.println(maxRPM);
    }

    targetRPM = rpm;

    if (targetRPM > 0) {
      lastSetRPM = targetRPM;
      motorRunning = true;
    } else {
      motorRunning = false;
    }

    Serial.print("Target RPM: ");
    Serial.println(targetRPM);
    zeroMessageShown = (targetRPM == 0);
    return;
  }

  // DIREZIONE
  if (cmd == "DIR:CW") {
    requestDirectionChange(true);
    return;
  }

  if (cmd == "DIR:CCW") {
    requestDirectionChange(false);
    return;
  }

  // MICROSTEPPING
  if (cmd.startsWith("MICROSTEP:")) {
    int m = cmd.substring(10).toInt();
    setMicrostepValue(m);
    return;
  }
}


// --------------------------------------
// MICROSTEPPING + MAX RPM
// --------------------------------------
void setMicrostepValue(int m) {

  if (m == 1 || m == 2 || m == 4 || m == 8 || m == 16 || m == 32 || m == 64) {
    microstep = m;
  } else {
    Serial.println("⚠ Microstep non valido. Ignorato.");
  }

  stepsPerRev = fullStepsPerRev * microstep;

  recalcMaxRPM();

  Serial.print("Microstepping impostato: 1/");
  Serial.println(microstep);
  Serial.print("Steps per giro: ");
  Serial.println(stepsPerRev);
  Serial.print("RPM massimi consentiti: ");
  Serial.println(maxRPM);
  Serial.println();

  if (targetRPM > maxRPM) targetRPM = maxRPM;
  if (currentRPM > maxRPM) currentRPM = maxRPM;

  updateStepInterval();
}


void recalcMaxRPM() {
  float raw = (STEP_S_LIMIT / stepsPerRev) * 60.0;
  raw = 5.0 * round(raw / 5.0);
  if (raw < minRPM) raw = minRPM;
  maxRPM = raw;
}


// --------------------------------------
// SOFT-REVERSE
// --------------------------------------
void requestDirectionChange(bool newCW) {

  if (newCW == directionCW) {
    Serial.print("Direzione: ");
    Serial.println(newCW ? "orario" : "anti orario");
    return;
  }

  savedTargetRPM = lastSetRPM > 0 ? lastSetRPM : targetRPM;
  pendingDirectionCW = newCW;
  directionChangePending = true;

  targetRPM = 0;  // rallenta a 0 prima di invertire
}

void handleSoftReverse() {
  if (!directionChangePending) return;

  if (currentRPM <= 0.2) {
    directionCW = pendingDirectionCW;
    digitalWrite(DIR_PIN, directionCW ? HIGH : LOW);

    Serial.print("Direzione: ");
    Serial.println(directionCW ? "orario" : "anti orario");

    directionChangePending = false;

    targetRPM = savedTargetRPM;
    lastSetRPM = savedTargetRPM;
  }
}


// --------------------------------------
// SOFT-START / SOFT-STOP
// --------------------------------------
void updateSoftStart() {

  unsigned long now = millis();
  unsigned long dtMillis = now - lastRampUpdateMillis;
  if (dtMillis == 0) return;
  lastRampUpdateMillis = now;

  float dt = dtMillis / 1000.0;
  float accel = accelProfiles[accelProfile];

  float diff = targetRPM - currentRPM;

  if (abs(diff) < 0.1) {
    currentRPM = targetRPM;
    updateStepInterval();
    return;
  }

  float maxDelta = accel * dt;
  if (diff > maxDelta) diff = maxDelta;
  else if (diff < -maxDelta) diff = -maxDelta;

  currentRPM += diff;

  if (currentRPM < 0) currentRPM = 0;

  updateStepInterval();
}


// --------------------------------------
// STEP TIME CALC
// --------------------------------------
void updateStepInterval() {
  if (currentRPM <= 0) {
    stepIntervalMicros = 0;
    return;
  }

  float rps = currentRPM / 60.0;
  float sps = rps * stepsPerRev;
  if (sps < 1) sps = 1;

  stepIntervalMicros = 1000000.0 / sps;
}


// --------------------------------------
// STEP MOTOR
// --------------------------------------
void stepMotorIfNeeded() {

  if (stepIntervalMicros <= 0) return;

  if (micros() - lastStepMicros >= stepIntervalMicros) {

    lastStepMicros = micros();

    digitalWrite(STEP_PIN, HIGH);
    delayMicroseconds(2);
    digitalWrite(STEP_PIN, LOW);
  }
}


// --------------------------------------
// TELEMETRIA LIVE per GUI
// --------------------------------------
void sendTelemetry() {
  unsigned long now = millis();
  if (now - lastTelemetryMillis < 50) return;  // ogni 50ms

  lastTelemetryMillis = now;

  Serial.print("CURRENT:");
  Serial.println(currentRPM);
}
