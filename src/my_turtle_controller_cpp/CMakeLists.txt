cmake_minimum_required(VERSION 3.8)
project(my_turtle_controller_cpp)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options("-Wall" "-Wextra" "-Wpedantic")
endif()

# --- 의존성 패키지 찾기 ---
# (4개 노드에 필요한 모든 재료를 찾습니다)
find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(turtlesim REQUIRED)
find_package(sensor_msgs REQUIRED)
find_package(ackermann_msgs REQUIRED)
find_package(ride_service_interfaces REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(nav_msgs REQUIRED)
find_package(visualization_msgs REQUIRED)

# --- 1. draw_square_node 빌드 설정 ---
add_executable(
  draw_square_node
  src/draw_square.cpp
)
ament_target_dependencies(
  draw_square_node
  rclcpp
  geometry_msgs
)

# --- 2. wall_avoider_node 빌드 설정 ---
add_executable(
  wall_avoider_node
  src/wall_avoider.cpp
)
ament_target_dependencies(
  wall_avoider_node
  rclcpp
  geometry_msgs
  turtlesim
)

# --- 3. obstacle_avoider_node 빌드 설정 ---
add_executable(
  obstacle_avoider_node
  src/obstacle_avoider.cpp
)
ament_target_dependencies(
  obstacle_avoider_node
  rclcpp
  sensor_msgs
  ackermann_msgs
)

# --- 4. wall_follower_node 빌드 설정 ---
add_executable(
  wall_follower_node
  src/wall_follower.cpp
)
ament_target_dependencies(
  wall_follower_node
  rclcpp
  sensor_msgs
  ackermann_msgs
)

add_executable(
  ride_service_manager
  src/ride_service_manager.cpp
)
ament_target_dependencies(
  ride_service_manager
  rclcpp
  ride_service_interfaces
  geometry_msgs
  ackermann_msgs
  sensor_msgs
  turtlesim
  nav_msgs
  visualization_msgs
)
# --- [핵심!] 설치(Install) 설정 ---

install(
  TARGETS
  draw_square_node
  wall_avoider_node
  obstacle_avoider_node
  wall_follower_node
  ride_service_manager
  DESTINATION lib/${PROJECT_NAME}
)

# --- Linter 설정 (기존) ---
install(
  FILES package.xml
  DESTINATION share/${PROJECT_NAME}
)

if(BUILD_TESTING)
  find_package(ament_lint_auto REQUIRED)
  ament_lint_auto_find_test_dependencies()
endif()

ament_package()
