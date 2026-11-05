import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// 家属模式（同一个 APK 的另一种界面）：看今天进度、替老人确认、看告警
Item {
    id: page
    property var model
    property var host
    property var stack

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 22
        spacing: 14

        RowLayout {
            Layout.fillWidth: true
            Text {
                text: qsTr("家属模式")
                font.pixelSize: 34
                font.bold: true
                color: host.ink
            }
            Item { Layout.fillWidth: true }
            Button {
                text: qsTr("切回老人")
                font.pixelSize: 20
                onClicked: { host.mode = "elder"; stack.replace(Qt.resolvedUrl("TodayPage.qml")) }
            }
        }

        Text {
            text: qsTr("今日 %1 条，已完成 %2 条").arg(model.todayList.length).arg(model.doneCount)
            font.pixelSize: 22
            color: host.soft
        }

        ListView {
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            model: model.todayList
            delegate: Rectangle {
                width: ListView.view.width
                height: 96
                radius: 12
                color: "#fbfcfe"
                border.width: 2
                border.color: "#e8eef7"
                RowLayout {
                    anchors.fill: parent
                    anchors.margins: 12
                    spacing: 10
                    Text { text: modelData.slot.substring(11); font.pixelSize: 22; color: host.soft }
                    Text {
                        text: modelData.title; font.pixelSize: 22; font.bold: true; color: host.ink
                        Layout.fillWidth: true; elide: Text.ElideRight
                    }
                    Text {
                        text: modelData.state === "confirmed" ? qsTr("已完成")
                            : modelData.state === "missed" ? qsTr("未确认") : qsTr("待提醒")
                        font.pixelSize: 20
                        color: modelData.state === "confirmed" ? "#0e5b33"
                             : modelData.state === "missed" ? "#7e1b22" : host.soft
                    }
                    Button {
                        text: qsTr("代确认")
                        font.pixelSize: 20
                        visible: modelData.state !== "confirmed"
                        onClicked: model.confirm(modelData.id)   // 真接口：POST /occurrences/{id}/events
                    }
                }
            }
        }

        Text {
            text: qsTr("提醒不丢靠服务端：断网/重启/改时间都以服务端状态为准。")
            font.pixelSize: 18
            color: host.soft
            wrapMode: Text.Wrap
            Layout.fillWidth: true
        }
    }
}
