import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// 记录页：点一下记两样（喝水 / 入睡 / 起床），配今日小统计
Item {
    id: page
    property var model
    property var host
    property var stack

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 22
        spacing: 16

        Text {
            text: qsTr("快速记录")
            font.pixelSize: 28
            font.bold: true
            color: host.ink
        }

        Repeater {
            model: [
                { t: qsTr("喝水 200ml"), type: "water", v: 200, u: "ml" },
                { t: qsTr("准备睡觉"), type: "sleep_start", v: 0, u: "" },
                { t: qsTr("起床了"), type: "sleep_end", v: 0, u: "" }
            ]
            delegate: Button {
                Layout.fillWidth: true
                Layout.preferredHeight: host.tap
                text: modelData.t
                font.pixelSize: 30
                font.bold: true
                background: Rectangle { color: "#fff"; radius: 16; border.width: 3; border.color: host.accent }
                contentItem: Text {
                    text: parent.text; color: host.accent; font: parent.font
                    horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter
                }
                // 真接口：POST /api/v1/records {elder_id, type, value, unit, at(ISO)}
                onClicked: toast.show(qsTr("已记下：%1").arg(modelData.t))
            }
        }

        Text {
            text: qsTr("近 7 天")
            font.pixelSize: 28
            font.bold: true
            color: host.ink
        }

        RowLayout {
            spacing: 12
            Rectangle {
                Layout.fillWidth: true
                height: 110
                radius: 14
                color: "#fff"; border.width: 2; border.color: "#e8eef7"
                Column {
                    anchors.centerIn: parent
                    Text { text: qsTr("已完成"); font.pixelSize: 20; color: host.soft }
                    Text { text: model.doneCount; font.pixelSize: 40; font.bold: true; color: host.ink }
                }
            }
            Rectangle {
                Layout.fillWidth: true
                height: 110
                radius: 14
                color: "#fff"; border.width: 2; border.color: "#e8eef7"
                Column {
                    anchors.centerIn: parent
                    Text { text: qsTr("今天的实例"); font.pixelSize: 20; color: host.soft }
                    Text { text: model.todayList.length; font.pixelSize: 40; font.bold: true; color: host.ink }
                }
            }
        }

        Item { Layout.fillHeight: true }

        Button {
            Layout.fillWidth: true
            Layout.preferredHeight: 64
            text: qsTr("返回今天")
            font.pixelSize: 24
            background: Rectangle { color: "#fff"; radius: 14; border.width: 2; border.color: host.accent }
            contentItem: Text {
                text: parent.text; color: host.accent; font: parent.font
                horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter
            }
            onClicked: stack.pop()
        }
    }

    ToolTip {
        id: toast
        visible: false
        text: ""
        timeout: 2000
        function show(msg) { text = msg; visible = true; }
    }
}
