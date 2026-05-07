if [ "$1" == "pull" ]; then # dc pull [-b]: docker compose pull && docker compose up -d [--build]
  sudo docker compose pull

  if [ "$2" == "-b" ] || [ "$2" == "--build" ]; then
    sudo docker compose up -d --build
  else
    sudo docker compose up -d
  fi
elif [ "$1" == "up" ]; then # dc up [-b]: docker compose up -d [--build]
  if [ "$2" == "-b" ] || [ "$2" == "--build" ]; then
    sudo docker compose up -d --build
  else
    sudo docker compose up -d
  fi
elif [ "$1" == "down" ]; then # dc down: docker compose down
  sudo docker compose down
elif [ "$1" == "logs" ]; then # dc down [n]: docker compose logs -fn [n | 100]
  sudo docker compose logs -fn "${2:-100}"
elif [ "$1" == "exec" ]; then # dc exec <id> [cmd]: docker exec -it <id> [cmd | bash]
  sudo docker exec -it "$id" "${cmd:-bash}"
elif [ "$1" == "ps" ]; then # dc ps: docker ps
  sudo docker ps
else
  echo "Usage: $0 pull [-b | --build]"
  echo "       $0 up [-b | --build]"
  echo "       $0 down"
  echo "       $0 logs [num]"
  echo "       $0 exec <id> [cmd]"
  echo "       $0 ps"
fi
