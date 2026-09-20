import QtQuick
import QtQuick.Controls

Rectangle {
    id: root
    width: 1920
    height: 1200
    color: "#060A14"

    readonly property color cyan: "#2ED3D7"
    readonly property color cyanDim: Qt.rgba(0.18, 0.83, 0.84, 0.55)
    readonly property color navy: Qt.rgba(0.024, 0.039, 0.078, 0.72)
    readonly property color red: "#E5432B"
    readonly property string mono: "JetBrains Mono"
    readonly property string cjk: "Noto Sans CJK JP"

    property bool denied: false

    Image {
        anchors.fill: parent
        source: config.Background
        fillMode: Image.PreserveAspectCrop
        asynchronous: false
    }

    // Everything below is laid out for a 1200-unit-high screen and scaled to the real one.
    Item {
        id: ui
        property real k: root.height / 1200
        width: root.width / k
        height: 1200
        scale: k
        transformOrigin: Item.TopLeft

        // ── corner brackets ─────────────────────────────────────────
        Repeater {
            model: [
                { x: 40, y: 40, ax: 1, ay: 1 },
                { x: 40, y: 40, ax: -1, ay: 1 },
                { x: 40, y: 40, ax: 1, ay: -1 },
                { x: 40, y: 40, ax: -1, ay: -1 }
            ]
            delegate: Item {
                x: modelData.ax > 0 ? modelData.x : ui.width - modelData.x
                y: modelData.ay > 0 ? modelData.y : ui.height - modelData.y
                Rectangle {
                    width: 34; height: 3; color: root.cyan
                    x: modelData.ax > 0 ? 0 : -width
                    y: modelData.ay > 0 ? 0 : -height
                }
                Rectangle {
                    width: 3; height: 34; color: root.cyan
                    x: modelData.ax > 0 ? 0 : -width
                    y: modelData.ay > 0 ? 0 : -height
                }
            }
        }

        // ── top strip ───────────────────────────────────────────────
        Text {
            x: 90; y: 34
            text: "公安9課  //  SECTION 9"
            color: root.cyan
            font.family: root.cjk
            font.pixelSize: 20
        }
        Text {
            anchors.right: parent.right; anchors.rightMargin: 90
            y: 36
            text: sddm.hostName ? "HOST://" + sddm.hostName.toUpperCase() : ""
            color: root.cyanDim
            font.family: root.mono
            font.pixelSize: 18
        }

        // ── clock column ────────────────────────────────────────────
        Text {
            id: clock
            x: 84; y: ui.height / 2 - 260
            color: root.cyan
            font.family: root.mono
            font.weight: Font.ExtraBold
            font.pixelSize: 150
            text: Qt.formatDateTime(new Date(), "HH:mm")
        }
        Text {
            id: dateLine
            x: 92; y: clock.y + clock.height + 4
            color: root.cyanDim
            font.family: root.mono
            font.pixelSize: 20
            text: Qt.formatDateTime(new Date(), "yyyy.MM.dd  //  dddd").toUpperCase()
        }
        Timer {
            interval: 1000; running: true; repeat: true
            onTriggered: {
                var now = new Date()
                clock.text = Qt.formatDateTime(now, "HH:mm")
                dateLine.text = Qt.formatDateTime(now, "yyyy.MM.dd  //  dddd").toUpperCase()
            }
        }

        Rectangle {
            x: 92; y: dateLine.y + 50
            width: 330; height: 1
            color: root.cyanDim
        }
        Text {
            id: prompt
            x: 92; y: dateLine.y + 70
            color: root.denied ? root.red : root.cyan
            font.family: root.mono
            font.pixelSize: 18
            text: root.denied ? "> ACCESS DENIED" : "> AUTHENTICATION REQUIRED"
        }

        // ── credentials ─────────────────────────────────────────────
        TextField {
            id: userField
            x: 92; y: prompt.y + 44
            width: 330; height: 46
            text: userModel.lastUser
            placeholderText: "▮ USERNAME"
            color: root.cyan
            placeholderTextColor: root.cyanDim
            font.family: root.mono
            font.pixelSize: 16
            leftPadding: 14
            selectionColor: root.cyan
            selectedTextColor: "#060A14"
            background: Rectangle {
                color: root.navy
                border.width: 1
                border.color: userField.activeFocus ? root.cyan : root.cyanDim
            }
            KeyNavigation.tab: passField
            onAccepted: passField.forceActiveFocus()
        }
        TextField {
            id: passField
            x: 92; y: userField.y + 56
            width: 330; height: 46
            echoMode: TextInput.Password
            passwordCharacter: "■"
            placeholderText: "▮ ENTER PASSPHRASE"
            color: root.cyan
            placeholderTextColor: root.cyanDim
            font.family: root.mono
            font.pixelSize: 16
            leftPadding: 14
            selectionColor: root.cyan
            selectedTextColor: "#060A14"
            focus: true
            background: Rectangle {
                color: root.navy
                border.width: 1
                border.color: root.denied ? root.red : (passField.activeFocus ? root.cyan : root.cyanDim)
            }
            KeyNavigation.backtab: userField
            onAccepted: sddm.login(userField.text, passField.text, sessionBox.currentIndex)
            Keys.onPressed: function(event) { root.denied = false }
        }

        ComboBox {
            id: sessionBox
            x: 92; y: passField.y + 56
            width: 330; height: 40
            model: sessionModel
            textRole: "name"
            currentIndex: sessionModel.lastIndex
            font.family: root.mono
            font.pixelSize: 14
            contentItem: Text {
                leftPadding: 14
                text: "SESSION: " + sessionBox.displayText.toUpperCase()
                color: root.cyanDim
                font: sessionBox.font
                verticalAlignment: Text.AlignVCenter
                elide: Text.ElideRight
            }
            indicator: Text {
                x: sessionBox.width - width - 12
                anchors.verticalCenter: parent.verticalCenter
                text: "▾"
                color: root.cyanDim
                font.pixelSize: 14
            }
            background: Rectangle {
                color: "transparent"
                border.width: 1
                border.color: sessionBox.activeFocus ? root.cyan : Qt.rgba(0.18, 0.83, 0.84, 0.3)
            }
            delegate: ItemDelegate {
                width: sessionBox.width
                height: 36
                contentItem: Text {
                    leftPadding: 10
                    text: model.name
                    color: highlighted ? "#060A14" : root.cyan
                    font: sessionBox.font
                    verticalAlignment: Text.AlignVCenter
                }
                background: Rectangle { color: highlighted ? root.cyan : "#0C1A33" }
                highlighted: sessionBox.highlightedIndex === index
            }
            popup: Popup {
                y: sessionBox.height + 2
                width: sessionBox.width
                padding: 1
                contentItem: ListView {
                    clip: true
                    implicitHeight: contentHeight
                    model: sessionBox.popup.visible ? sessionBox.delegateModel : null
                }
                background: Rectangle { color: "#0C1A33"; border.width: 1; border.color: root.cyan }
            }
        }

        Connections {
            target: sddm
            function onLoginFailed() {
                root.denied = true
                passField.text = ""
                passField.forceActiveFocus()
            }
        }

        // ── bottom strip: power actions ─────────────────────────────
        Row {
            anchors.right: parent.right; anchors.rightMargin: 90
            y: ui.height - 66
            spacing: 26
            Repeater {
                model: [
                    { label: "SUSPEND",  ok: sddm.canSuspend,  act: function() { sddm.suspend() } },
                    { label: "REBOOT",   ok: sddm.canReboot,   act: function() { sddm.reboot() } },
                    { label: "SHUTDOWN", ok: sddm.canPowerOff, act: function() { sddm.powerOff() } }
                ]
                delegate: Text {
                    visible: modelData.ok
                    text: "[ " + modelData.label + " ]"
                    color: area.containsMouse ? root.cyan : root.cyanDim
                    font.family: root.mono
                    font.pixelSize: 16
                    MouseArea {
                        id: area
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: modelData.act()
                    }
                }
            }
        }
        Text {
            x: 90; y: ui.height - 66
            text: "SESSION LOCKED"
            color: root.cyanDim
            font.family: root.mono
            font.pixelSize: 15
        }

    }

    Component.onCompleted: passField.forceActiveFocus()
}
