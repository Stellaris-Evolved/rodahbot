#!/bin/bash

# Build the SAM application
sam build --use-container

# Deploy the SAM application
sam deploy
