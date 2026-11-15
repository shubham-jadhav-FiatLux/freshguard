PLUGIN := freshguard
OUT := build/$(PLUGIN).so

.PHONY: build test vet clean

build:
	CGO_ENABLED=1 go build -buildmode=plugin -o $(OUT) .

test:
	go test -v ./...

vet:
	go vet ./...

clean:
	rm -rf build
