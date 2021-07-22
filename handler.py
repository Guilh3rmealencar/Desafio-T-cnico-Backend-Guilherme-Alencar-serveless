
import boto3
from boto3.dynamodb.conditions import Key
import simplejson as json
import pprint
from PIL import Image
import io
import os
from urllib.parse import unquote_plus
import base64

dynamodb = boto3.resource("dynamodb")
s3 = boto3.resource("s3")
dynamodbResource = boto3.resource("dynamodb")

def extractMetadata(event, context):

# Extrai metadados de objetos carregados no bucket.
# É salva na tabela de metadados (nome = variável de ambiente 'DYNAMODB_TABLE').
# Metadados salvos: s3objectkey, size, type, width e height

    bucketName = event["Records"][0]["s3"]["bucket"]["name"]
    objectKey = unquote_plus(event["Records"][0]["s3"]["object"]["key"])
    objectSize = event["Records"][0]["s3"]["object"]["size"]

    s3Obj = s3.Object(bucketName, objectKey)
    s3Response = s3Obj.get()

    imageBin = s3Response["Body"].read()
    imageStream = io.BytesIO(imageBin)
    image = Image.open(imageStream)

    dbResponse = dynamodb.batch_write_item(
        RequestItems={
            os.environ["DYNAMODB_TABLE"]: [
                {
                    "PutRequest": {
                        "Item": {
                            "s3objectkey": objectKey,
                            "size": objectSize,
                            "type": s3Obj.content_type,
                            "width": image.width,
                            "height": image.height
                        }
                    }
                }
            ]
        }
    )

    if dbResponse["ResponseMetadata"]["HTTPStatusCode"] == 200:
        print("Sucesso!")
    else:
        pprint.pp(dbResponse)

    io.IOBase.close(imageStream)

def getMetadata(event, context):

# Retorna uma resposta com os metadados sobre o item pedido.
# Deve conter uma 's3objectkey' dentro de 'pathParameters',com a object key da imagem.
# O codigo 'response', com 'statusCode',e corpo em JSON com uma mensagem, os metadados e o evento.

    s3ObjectMetadata = {}

    try:
        s3ObjectKey = "uploads/" + event["pathParameters"]["s3objectkey"]  #
        dbResponse = dynamodbResource.Table(os.environ["DYNAMODB_TABLE"]).query(
            KeyConditionExpression=Key("s3objectkey").eq(s3ObjectKey)
        )

        if dbResponse["Count"] > 0:
            s3ObjectMetadata = dbResponse["Items"][0]
            message = "Objeto nao foi encontrado!"
            statusCode = 200
        else:
            message = "Objeto nao foi encontrado!"
            statusCode = 404
    except TypeError:
        message = "Falhou o s3objectkey!"
        statusCode = 400
    except Exception as e:
        message = str(e)
        statusCode = 500

    body = {
        "message": message,
        "s3ObjectMetadata": s3ObjectMetadata,
        "input": event
    }
    response = {
        "statusCode": statusCode,
        "body": json.dumps(body)
    }

    return response


def getImage(event, context):

# Retorna uma resposta com a imagem pedida.
# Deve conter uma 's3objectkey' dentro de 'pathParameters',com a object key da imagem.
# O codigo 'response', com 'statusCode' e a biblioteca base64 contendo a imagem em si ou em um texto contendo uma mensagem

    contentType = "application/json"
    contentDisposition = "inline"
    isBase64Encoded = False

    try:
        s3ObjectKey = "uploads/" + event["pathParameters"]["s3objectkey"]  #
        bucketName = "instagraoguilhermealencar"

        s3Obj = s3.Object(bucketName, s3ObjectKey)
        s3Response = s3Obj.get()
        imageBin = s3Response["Body"].read()

        contentType = s3Obj.content_type
        contentDisposition = "attachment"
        isBase64Encoded = True
        body = base64.b64encode(imageBin).decode("utf-8")
        statusCode = 200
    except TypeError:
        body = "Falhou o s3objectkey!"
        statusCode = 400
    except Exception as e:
        body = str(e)
        statusCode = 500

    response = {
        "statusCode": statusCode,
        "isBase64Encoded": isBase64Encoded,
        "headers": {
            "Content-Type": contentType,
            "Content-Disposition": contentDisposition
        },
        "body": body
    }

    return response
def infoImages(event, context):

# Retorna informações sobre as imagens cujos metadados estão armazenados.
# O codigo 'response', com 'statusCode' e a biblioteca em JSON.
# Com as informaçoes sobre a maior imagem, a menor ,os tipos e quantidade de cada tipo.


    stats = {}
    try:
        biggest = {"s3objectkey": "", "size": 0} #A imagem que contem o maior tamanho.
        smallest = {"s3objectkey": "", "size": float("inf")} #A imagem que contem o menor tamanho.
        types = dict() #A imagem que contem os tipos de imagens salvas é a quantidade de cada tipo de imagem salva.

        results = dynamodbResource.Table(os.environ["DYNAMODB_TABLE"]).scan()
        while True:
            for item in results["Items"]:
                if biggest["size"] < item["size"]:
                    biggest["s3objectkey"] = item["s3objectkey"]
                    biggest["size"] = item["size"] #A imagem que contem o maior tamanho.
                if item["size"] < smallest["size"]:
                    smallest["s3objectkey"] = item["s3objectkey"]
                    smallest["size"] = item["size"] #A imagem que contem o menor tamanho.
                if item["type"] in types:
                    types[item["type"]] += 1
                else:
                    types[item["type"]] = 1#A imagem que contem os tipos de imagens salvas é a quantidade de cada tipo de imagem salva.

            if "LastEvaluatedKey" not in results:
                break
            results = dynamodbResource.Table(os.environ["DYNAMODB_TABLE"]).scan(
                ExclusiveStartKey=results["LastEvaluatedKey"])

        stats = {
            "biggest": biggest,
            "smallest": smallest,
            "types": types
        }

        message = "Done!"
        statusCode = 200

    except Exception as e:
        message = str(e)
        statusCode = 500

    body = {
        "message": message,
        "stats": stats,
        "input": event
    }
    response = {
        "statusCode": statusCode,
        "body": json.dumps(body)
    }

    return response