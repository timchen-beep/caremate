// 作用：Qt 外壳：三 tab 布局、字号/按钮尺寸常量（32px 正文、84px 按钮）
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ApplicationWindow {
    id: root
    width: 412
    height: 915
    visible: true
    title: qsTr("CareMate")
    color: "#ffffff"
    // 老人端：状态栏与导航栏尽量藏起来（普通 App 只能请求沉浸式，真正隐藏需 root）
    flags: Qt.Window | Qt.FramelessWindowHint

    // 契约：正文 ≥24、主按钮 ≥48（这里用 84），对比 ≥7:1
    readonly property int fsBody: 24
    readonly property int fsTitle: 44
    readonly property int tap: 84
    readonly property color ink: "#14264a"
    readonly property color soft: "#3a4a63"
    readonly property color accent: "#24457a"
    readonly property color danger: "#7e1b22"

    property string mode: "elder"      // elder | family

    StackView {
        id: stack
        anchors.fill: parent
        initialItem: mode === "elder" ? todayPage : familyPage
    }

    Component { id: todayPage; TodayPage { model: caremate; host: root; stack: stack } }
    Component { id: recordPage; RecordPage { model: caremate; host: root; stack: stack } }
    Component { id: familyPage; FamilyPage { model: caremate; host: root; stack: stack } }

    // 底部三个大 tab（老人端只有今天/记录/我的）
    footer: Rectangle {
        height: 96
        color: "#ffffff"
        border.width: 2
        border.color: "#e8eef7"
        RowLayout {
            anchors.fill: parent
            Repeater {
                model: [
                    { t: "今天", icon: "🔔" },
                    { t: "记录", icon: "📋" },
                    { t: "我的", icon: "⚙️" }
                ]
                delegate: Item {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    Column {
                        anchors.centerIn: parent
                        spacing: 2
                        Text { text: modelData.icon; font.pixelSize: 26; anchors.horizontalCenter: parent.horizontalCenter }
                        Text {
                            text: modelData.t
                            font.pixelSize: 20
                            color: root.soft
                            anchors.horizontalCenter: parent.horizontalCenter
                        }
                    }
                    MouseArea {
                        anchors.fill: parent
                        onClicked: {
                            if (index === 0) stack.replace(todayPage)
                            else if (index === 1) stack.replace(recordPage)
                            else root.mode = (root.mode === "elder" ? "family" : "elder"),
                                 stack.replace(familyPage)
                        }
                    }
                }
            }
        }
    }
}
