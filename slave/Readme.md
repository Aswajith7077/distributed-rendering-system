

```bash
docker buildx build --platform linux/arm64 --load -t dre-slave:latest .    
```


For the given number of replicas we need that many number of workers

```bash
docker-compose up --scale worker=2
```

Clean up local docker, better if you mess up with duplicated containers

```bash
docker compose down --remove-orphans
docker system prune -f
```