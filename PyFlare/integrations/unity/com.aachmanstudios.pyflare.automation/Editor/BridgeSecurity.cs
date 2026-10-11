using System;
using System.IO;
using System.Net;
using System.Text;

namespace AachmanStudios.PyFlare.Unity
{
    internal static class BridgeSecurity
    {
        internal const int MaximumRequestBytes = 1_048_576;

        internal static bool IsLoopback(HttpListenerRequest request)
        {
            var endpoint = request.RemoteEndPoint;
            return endpoint != null && IPAddress.IsLoopback(endpoint.Address);
        }

        internal static bool TokenEquals(string expected, string supplied)
        {
            if (expected == null || supplied == null)
            {
                return false;
            }

            var expectedBytes = Encoding.UTF8.GetBytes(expected);
            var suppliedBytes = Encoding.UTF8.GetBytes(supplied);
            var difference = expectedBytes.Length ^ suppliedBytes.Length;
            var maximum = Math.Max(expectedBytes.Length, suppliedBytes.Length);

            for (var index = 0; index < maximum; index++)
            {
                var left = index < expectedBytes.Length ? expectedBytes[index] : (byte)0;
                var right = index < suppliedBytes.Length ? suppliedBytes[index] : (byte)0;
                difference |= left ^ right;
            }

            return difference == 0;
        }

        internal static string ReadBody(HttpListenerRequest request)
        {
            if (request.ContentLength64 > MaximumRequestBytes)
            {
                throw new InvalidDataException("request_too_large");
            }

            using (var buffer = new MemoryStream())
            {
                var chunk = new byte[16_384];
                int read;
                while ((read = request.InputStream.Read(chunk, 0, chunk.Length)) > 0)
                {
                    if (buffer.Length + read > MaximumRequestBytes)
                    {
                        throw new InvalidDataException("request_too_large");
                    }

                    buffer.Write(chunk, 0, read);
                }

                return new UTF8Encoding(false, true).GetString(buffer.ToArray());
            }
        }
    }
}
