# 作用：Qt 工程构建：QML 模块声明、Android 包源码目录
cmake_minimum_required(VERSION 3.21)
project(CareMate VERSION 1.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_AUTOMOC ON)
set(CMAKE_AUTORCC ON)

find_package(Qt6 6.5 REQUIRED COMPONENTS Quick Network)

qt_standard_project_setup()

# ---------------------------------------------------------------- 主程序
qt_add_executable(appCareMate
    main.cpp
    core/ReminderModel.cpp
    core/ReminderModel.h
)

qt_add_qml_module(appCareMate
    URI CareMate
    VERSION 1.0
    QML_FILES
        main.qml
        pages/TodayPage.qml
        pages/RecordPage.qml
        pages/FamilyPage.qml
        pages/SosButton.qml
    SOURCES
        core/ReminderModel.h
)

find_package(Qt6 REQUIRED COMPONENTS Core)
target_link_libraries(appCareMate PRIVATE Qt6::Quick Qt6::Network)

# ---------------------------------------------------------------- Android 部分
# 说明：Qt for Android 的 Java/JNI 代码放在 android/ 下，由 Qt 的 build.gradle 引入。
# 没有 NDK 时这里什么都不做，普通桌面构建仍可跑（用于在电脑上先看 QML 布局）。
if(ANDROID)
    set(ANDROID_PACKAGE_SOURCE_DIR "${CMAKE_CURRENT_SOURCE_DIR}/android")
    message(STATUS "Android 构建：会合并 android/AndroidManifest.xml 与 jni/AlarmBridge")
endif()

install(TARGETS appCareMate
    BUNDLE DESTINATION .
    RUNTIME DESTINATION ${CMAKE_INSTALL_BINDIR}
)

