
"use strict";

let SetAxis = require('./SetAxis.js')
let GetInt32 = require('./GetInt32.js')
let SetString = require('./SetString.js')
let MoveAxisAngle = require('./MoveAxisAngle.js')
let GetControllerDigitalIO = require('./GetControllerDigitalIO.js')
let GetErr = require('./GetErr.js')
let ClearErr = require('./ClearErr.js')
let SetFloat32 = require('./SetFloat32.js')
let SetDigitalIO = require('./SetDigitalIO.js')
let GetSetModbusData = require('./GetSetModbusData.js')
let GetFloat32List = require('./GetFloat32List.js')
let SetInt16 = require('./SetInt16.js')
let SetModbusTimeout = require('./SetModbusTimeout.js')
let TCPOffset = require('./TCPOffset.js')
let GetDigitalIO = require('./GetDigitalIO.js')
let Move = require('./Move.js')
let PlayTraj = require('./PlayTraj.js')
let ConfigToolModbus = require('./ConfigToolModbus.js')
let SetControllerAnalogIO = require('./SetControllerAnalogIO.js')
let MoveVelocity = require('./MoveVelocity.js')
let SetLoad = require('./SetLoad.js')
let GripperMove = require('./GripperMove.js')
let GetAnalogIO = require('./GetAnalogIO.js')
let FtIdenLoad = require('./FtIdenLoad.js')
let SetMultipleInts = require('./SetMultipleInts.js')
let GripperConfig = require('./GripperConfig.js')
let Call = require('./Call.js')
let SetToolModbus = require('./SetToolModbus.js')
let VacuumGripperCtrl = require('./VacuumGripperCtrl.js')
let GripperState = require('./GripperState.js')
let FtCaliLoad = require('./FtCaliLoad.js')
let MoveVelo = require('./MoveVelo.js')

module.exports = {
  SetAxis: SetAxis,
  GetInt32: GetInt32,
  SetString: SetString,
  MoveAxisAngle: MoveAxisAngle,
  GetControllerDigitalIO: GetControllerDigitalIO,
  GetErr: GetErr,
  ClearErr: ClearErr,
  SetFloat32: SetFloat32,
  SetDigitalIO: SetDigitalIO,
  GetSetModbusData: GetSetModbusData,
  GetFloat32List: GetFloat32List,
  SetInt16: SetInt16,
  SetModbusTimeout: SetModbusTimeout,
  TCPOffset: TCPOffset,
  GetDigitalIO: GetDigitalIO,
  Move: Move,
  PlayTraj: PlayTraj,
  ConfigToolModbus: ConfigToolModbus,
  SetControllerAnalogIO: SetControllerAnalogIO,
  MoveVelocity: MoveVelocity,
  SetLoad: SetLoad,
  GripperMove: GripperMove,
  GetAnalogIO: GetAnalogIO,
  FtIdenLoad: FtIdenLoad,
  SetMultipleInts: SetMultipleInts,
  GripperConfig: GripperConfig,
  Call: Call,
  SetToolModbus: SetToolModbus,
  VacuumGripperCtrl: VacuumGripperCtrl,
  GripperState: GripperState,
  FtCaliLoad: FtCaliLoad,
  MoveVelo: MoveVelo,
};
