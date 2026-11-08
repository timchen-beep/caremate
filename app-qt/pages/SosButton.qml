// 作用：Qt 呼救按钮：按住 3 秒才触发，松手取消
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// 呼救：按住 3 秒才触发（对应后端 POST /api/v1/sos）
Button {
    id: sos
    property var host
    signal triggered()

    text: pressed ? qsTr("松手取消") : qsTr("按住呼救")
    font.pixelSize: 20
    font.bold: true
    Layout.preferredHeight: 60
    highlighted: false

    background: Rectangle {
        radius: 14
        color: sos.pressed ? "#a3282f" : "#7e1b22"
        // 进度条：按住时从左往右填满
        Rectangle {
            id: fill
            height: 6
            width: 0
            anchors.left: parent.left
            anchors.bottom: parent.bottom
            color: "#f6d5d8"
            radius: 3
        }
    }
    contentItem: Text {
        text: sos.text
        color: "#fff"
        font: sos.font
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
    }

    property var timer: null
    onPressedChanged: {
        if (pressed) {
            fill.width = 0
            timer = holdTimer
            holdTimer.restart()
            growAnim.restart()
        } else {
            holdTimer.stop()
            growAnim.stop()
            fill.width = 0
        }
    }

    Timer {
        id: holdTimer
        interval: 3000
        repeat: false
        onTriggered: {
            fill.width = 0
            sos.triggered()          // 真正发 SOS
        }
    }

    NumberAnimation {
        id: growAnim
        target: fill
        property: "width"
        from: 0
        to: sos.width
        duration: 3000
        running: false
    }
}
