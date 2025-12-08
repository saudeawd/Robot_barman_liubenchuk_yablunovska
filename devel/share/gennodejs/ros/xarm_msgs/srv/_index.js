
"use strict";

let GetAnalogIO = require('./GetAnalogIO.js')
let MoveAxisAngle = require('./MoveAxisAngle.js')
let GripperMove = require('./GripperMove.js')
let Move = require('./Move.js')
let FtIdenLoad = require('./FtIdenLoad.js')
let GetControllerDigitalIO = require('./GetControllerDigitalIO.js')
let FtCaliLoad = require('./FtCaliLoad.js')
let SetInt16 = require('./SetInt16.js')
let SetToolModbus = require('./SetToolModbus.js')
let TCPOffset = require('./TCPOffset.js')
let GetInt32 = require('./GetInt32.js')
let GripperConfig = require('./GripperConfig.js')
let PlayTraj = require('./PlayTraj.js')
let GripperState = require('./GripperState.js')
let SetDigitalIO = require('./SetDigitalIO.js')
let VacuumGripperCtrl = require('./VacuumGripperCtrl.js')
let MoveVelocity = require('./MoveVelocity.js')
let SetModbusTimeout = require('./SetModbusTimeout.js')
let GetErr = require('./GetErr.js')
let ClearErr = require('./ClearErr.js')
let Call = require('./Call.js')
let SetControllerAnalogIO = require('./SetControllerAnalogIO.js')
let SetLoad = require('./SetLoad.js')
let GetSetModbusData = require('./GetSetModbusData.js')
let SetMultipleInts = require('./SetMultipleInts.js')
let GetFloat32List = require('./GetFloat32List.js')
let SetString = require('./SetString.js')
let GetDigitalIO = require('./GetDigitalIO.js')
let MoveVelo = require('./MoveVelo.js')
let SetAxis = require('./SetAxis.js')
let SetFloat32 = require('./SetFloat32.js')
let ConfigToolModbus = require('./ConfigToolModbus.js')

module.exports = {
  GetAnalogIO: GetAnalogIO,
  MoveAxisAngle: MoveAxisAngle,
  GripperMove: GripperMove,
  Move: Move,
  FtIdenLoad: FtIdenLoad,
  GetControllerDigitalIO: GetControllerDigitalIO,
  FtCaliLoad: FtCaliLoad,
  SetInt16: SetInt16,
  SetToolModbus: SetToolModbus,
  TCPOffset: TCPOffset,
  GetInt32: GetInt32,
  GripperConfig: GripperConfig,
  PlayTraj: PlayTraj,
  GripperState: GripperState,
  SetDigitalIO: SetDigitalIO,
  VacuumGripperCtrl: VacuumGripperCtrl,
  MoveVelocity: MoveVelocity,
  SetModbusTimeout: SetModbusTimeout,
  GetErr: GetErr,
  ClearErr: ClearErr,
  Call: Call,
  SetControllerAnalogIO: SetControllerAnalogIO,
  SetLoad: SetLoad,
  GetSetModbusData: GetSetModbusData,
  SetMultipleInts: SetMultipleInts,
  GetFloat32List: GetFloat32List,
  SetString: SetString,
  GetDigitalIO: GetDigitalIO,
  MoveVelo: MoveVelo,
  SetAxis: SetAxis,
  SetFloat32: SetFloat32,
  ConfigToolModbus: ConfigToolModbus,
};
