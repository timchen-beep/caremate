import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// 今天页：到点卡片 + 三个大按钮（对应后端 pending → confirmed / snoozed / missed）
Item {
    id: page
    property var model
    property var host
    property var stack

    readonly property var current: (model.dueList.length > 0) ? model.dueList[0] : null

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 22
        spacing: 16

        // 顶部：时间 + 呼救
        RowLayout {
            Layout.fillWidth: true
            Text {
                text: Qt.formatTime(new Date(), "HH:mm")
                font.pixelSize: host.fsTitle
                font.bold: true
                color: host.ink
            }
            Item { Layout.fillWidth: true }
            SosButton { host: host; onTriggered: model.sos() }
        }

        // 现在该做的事
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 360
            radius: 20
            color: current ? "#eef4fc" : "#fbfcfe"
            border.width: 3
            border.color: current ? "#9db4d4" : "#cbd7e8"

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 20
                spacing: 10

                Text {
                    text: current ? qsTr("现在该做的事") : qsTr("现在没有要做的事")
                    font.pixelSize: host.fsBody
                    color: host.soft
                }
                Text {
                    visible: !!current
                    text: current ? current.title : ""
                    font.pixelSize: host.fsTitle
                    font.bold: true
                    color: host.ink
                    wrapMode: Text.Wrap
                    Layout.fillWidth: true
                }
                Text {
                    visible: !!current
                    text: current ? qsTr("计划时间 %1%2").arg(current.slot.substring(11))
                                    .arg(current.lateMin > 0 ? qsTr("　已过 %1 分钟").arg(current.lateMin) : "")
                                  : qsTr("到点会自动提醒你")
                    font.pixelSize: host.fsBody
                    color: host.soft
                }

                Item { Layout.fillHeight: true }

                // 确认 / 等会儿 / 没做：三个 84 高的大按钮
                Button {
                    Layout.fillWidth: true
                    Layout.preferredHeight: host.tap
                    enabled: !!current
                    text: qsTr("吃了，记一下")
                    font.pixelSize: 30
                    font.bold: true
                    background: Rectangle { color: host.accent; radius: 16 }
                    contentItem: Text {
                        text: parent.text; color: "#fff"; font: parent.font
                        horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter
                    }
                    onClicked: model.confirm(current.id)
                }
                Button {
                    Layout.fillWidth: true
                    Layout.preferredHeight: host.tap
                    enabled: !!current
                    text: qsTr("等会儿再做")
                    font.pixelSize: 30
                    font.bold: true
                    background: Rectangle { color: "#fff"; radius: 16; border.width: 3; border.color: host.accent }
                    contentItem: Text {
                        text: parent.text; color: host.accent; font: parent.font
                        horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter
                    }
                    onClicked: model.snooze(current.id)
                }
                Button {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 72
                    enabled: !!current
                    text: qsTr("这次没做")
                    font.pixelSize: 26
                    font.bold: true
                    background: Rectangle { color: "#fff"; radius: 16; border.width: 3; border.color: host.danger }
                    contentItem: Text {
                        text: parent.text; color: host.danger; font: parent.font
                        horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter
                    }
                    onClicked: model.missed(current.id)
                }
            }
        }

        Text {
            text: qsTr("今天的计划（已完成 %1 条）").arg(model.doneCount)
            font.pixelSize: 26
            font.bold: true
            color: host.ink
        }

        ListView {
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            model: model.todayList
            delegate: RowLayout {
                width: ListView.view.width
                spacing: 10
                Text {
                    text: modelData.slot.substring(11)
                    font.pixelSize: host.fsBody
                    color: host.soft
                    Layout.preferredWidth: 80
                }
                Text {
                    text: modelData.title
                    font.pixelSize: host.fsBody
                    color: host.ink
                    Layout.fillWidth: true
                    elide: Text.ElideRight
                }
                Text {
                    text: modelData.state === "confirmed" ? qsTr("已完成")
                        : modelData.state === "missed" ? qsTr("未确认")
                        : modelData.state === "snoozed" ? qsTr("稍后") : qsTr("待提醒")
                    font.pixelSize: 20
                    color: modelData.state === "confirmed" ? "#0e5b33"
                         : modelData.state === "pending" ? host.soft : "#7e1b22"
                }
            }
        }
    }

    Component.onCompleted: model.refresh()
}
