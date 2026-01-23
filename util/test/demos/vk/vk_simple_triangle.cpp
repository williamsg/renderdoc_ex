/******************************************************************************
 * The MIT License (MIT)
 *
 * Copyright (c) 2018-2026 Baldur Karlsson
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy
 * of this software and associated documentation files (the "Software"), to deal
 * in the Software without restriction, including without limitation the rights
 * to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
 * copies of the Software, and to permit persons to whom the Software is
 * furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in
 * all copies or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 * IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 * FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
 * LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
 * OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
 * THE SOFTWARE.
 ******************************************************************************/

#include "vk_test.h"

RD_TEST(VK_Simple_Triangle, VulkanGraphicsTest)
{
  static constexpr const char *Description =
      "Just draws a simple triangle, using normal pipeline. Basic test that can be used "
      "for any dead-simple tests that don't require any particular API use";

  int main()
  {
    // initialise, create window, create context, etc
    if(!Init())
      return 3;

    VkPipelineLayout layout = createPipelineLayout(vkh::PipelineLayoutCreateInfo());

    vkh::GraphicsPipelineCreateInfo pipeCreateInfo;

    pipeCreateInfo.layout = layout;
    pipeCreateInfo.renderPass = mainWindow->rp;

    pipeCreateInfo.vertexInputState.vertexBindingDescriptions = {vkh::vertexBind(0, DefaultA2V)};
    pipeCreateInfo.vertexInputState.vertexAttributeDescriptions = {
        vkh::vertexAttr(0, 0, DefaultA2V, pos),
        vkh::vertexAttr(1, 0, DefaultA2V, col),
        vkh::vertexAttr(2, 0, DefaultA2V, uv),
    };

    pipeCreateInfo.stages = {
        CompileShaderModule(VKDefaultVertex, ShaderLang::glsl, ShaderStage::vert, "main"),
        CompileShaderModule(VKDefaultPixel, ShaderLang::glsl, ShaderStage::frag, "main"),
    };

    VkPipeline pipe = createGraphicsPipeline(pipeCreateInfo);

    AllocatedBuffer vb(
        this,
        vkh::BufferCreateInfo(sizeof(DefaultTri),
                              VK_BUFFER_USAGE_VERTEX_BUFFER_BIT | VK_BUFFER_USAGE_TRANSFER_DST_BIT),
        VmaAllocationCreateInfo({0, VMA_MEMORY_USAGE_CPU_TO_GPU}));

    vb.upload(DefaultTri);

    AllocatedImage offimg(this,
                          vkh::ImageCreateInfo(4, 4, 0, VK_FORMAT_R32G32B32A32_SFLOAT,
                                               VK_IMAGE_USAGE_TRANSFER_DST_BIT),
                          VmaAllocationCreateInfo({0, VMA_MEMORY_USAGE_GPU_ONLY}));

    AllocatedImage offimgMS(
        this,
        vkh::ImageCreateInfo(4, 4, 0, VK_FORMAT_R16G16B16A16_SFLOAT,
                             VK_IMAGE_USAGE_TRANSFER_DST_BIT, 1, 1, VK_SAMPLE_COUNT_4_BIT),
        VmaAllocationCreateInfo({0, VMA_MEMORY_USAGE_GPU_ONLY}));

    VkDebugUtilsObjectTagInfoEXT tag = {
        VK_STRUCTURE_TYPE_DEBUG_UTILS_OBJECT_TAG_INFO_EXT,
        NULL,
        VK_OBJECT_TYPE_INSTANCE,
        (uint64_t)instance,
        RENDERDOC_APIObjectAnnotationHelper,
        sizeof(instance),
        instance,
    };

    vkSetDebugUtilsObjectTagEXT(device, &tag);
    tag.objectHandle = (uint64_t)phys;
    tag.objectType = VK_OBJECT_TYPE_PHYSICAL_DEVICE;
    tag.pTag = phys;
    vkSetDebugUtilsObjectTagEXT(device, &tag);

    RENDERDOC_AnnotationValue val;

    rdoc->SetObjectAnnotation(RENDERDOC_DEVICEPOINTER_FROM_VKINSTANCE(instance), instance,
                              "someInstData", eRENDERDOC_Bool, 0, RDAnnotationHelper(true));
    rdoc->SetObjectAnnotation(RENDERDOC_DEVICEPOINTER_FROM_VKINSTANCE(instance), phys, "physData",
                              eRENDERDOC_String, 0, RDAnnotationHelper("my physical device ha ha"));

    rdoc->SetObjectAnnotation(RENDERDOC_DEVICEPOINTER_FROM_VKINSTANCE(instance), offimg.image,
                              "cool.secretInfo", eRENDERDOC_Float, 0, RDAnnotationHelper(3.14f));
    val.apiObject = offimgMS.image;
    rdoc->SetObjectAnnotation(RENDERDOC_DEVICEPOINTER_FROM_VKINSTANCE(instance), offimg.image,
                              "cool.otherimage", eRENDERDOC_APIObject, 0, &val);

    while(Running())
    {
      rdoc->SetCommandAnnotation(RENDERDOC_DEVICEPOINTER_FROM_VKINSTANCE(instance), queue,
                                 "global.coolQueue", eRENDERDOC_Bool, 0, RDAnnotationHelper(true));

      int counter = 1;
      rdoc->SetCommandAnnotation(RENDERDOC_DEVICEPOINTER_FROM_VKINSTANCE(instance), queue,
                                 "global.counter", eRENDERDOC_Int32, 0,
                                 RDAnnotationHelper(counter++));

      VkCommandBuffer cmd = GetCommandBuffer();

      vkBeginCommandBuffer(cmd, vkh::CommandBufferBeginInfo());

      VkImage swapimg =
          StartUsingBackbuffer(cmd, VK_ACCESS_TRANSFER_WRITE_BIT, VK_IMAGE_LAYOUT_GENERAL);

      rdoc->SetCommandAnnotation(RENDERDOC_DEVICEPOINTER_FROM_VKINSTANCE(instance), cmd,
                                 "global.counter", eRENDERDOC_Int32, 0,
                                 RDAnnotationHelper(counter++));

      rdoc->SetCommandAnnotation(RENDERDOC_DEVICEPOINTER_FROM_VKINSTANCE(instance), cmd,
                                 "global.coolCommand", eRENDERDOC_Bool, 0, RDAnnotationHelper(true));

      rdoc->SetCommandAnnotation(RENDERDOC_DEVICEPOINTER_FROM_VKINSTANCE(instance), cmd,
                                 "draw.isClear", eRENDERDOC_Bool, 0, RDAnnotationHelper(true));
      rdoc->SetCommandAnnotation(RENDERDOC_DEVICEPOINTER_FROM_VKINSTANCE(instance), cmd,
                                 "draw.clearingswap", eRENDERDOC_Float, 0, RDAnnotationHelper(1.1f));
      rdoc->SetCommandAnnotation(RENDERDOC_DEVICEPOINTER_FROM_VKINSTANCE(instance), cmd,
                                 "draw.notclearing", eRENDERDOC_APIObject, 0, &val);

      vkCmdClearColorImage(cmd, swapimg, VK_IMAGE_LAYOUT_GENERAL,
                           vkh::ClearColorValue(0.2f, 0.2f, 0.2f, 1.0f), 1,
                           vkh::ImageSubresourceRange());

      rdoc->SetCommandAnnotation(RENDERDOC_DEVICEPOINTER_FROM_VKINSTANCE(instance), cmd, "draw",
                                 eRENDERDOC_Empty, 0, NULL);

      vkh::cmdPipelineBarrier(
          cmd, {
                   vkh::ImageMemoryBarrier(0, VK_ACCESS_TRANSFER_WRITE_BIT, VK_IMAGE_LAYOUT_UNDEFINED,
                                           VK_IMAGE_LAYOUT_GENERAL, offimg.image),
               });

      rdoc->SetCommandAnnotation(RENDERDOC_DEVICEPOINTER_FROM_VKINSTANCE(instance), cmd,
                                 "global.counter", eRENDERDOC_Int32, 0,
                                 RDAnnotationHelper(counter++));

      vkCmdClearColorImage(cmd, offimg.image, VK_IMAGE_LAYOUT_GENERAL,
                           vkh::ClearColorValue(0.2f, 0.2f, 0.2f, 1.0f), 1,
                           vkh::ImageSubresourceRange());

      rdoc->SetCommandAnnotation(RENDERDOC_DEVICEPOINTER_FROM_VKINSTANCE(instance), cmd,
                                 "global.counter", eRENDERDOC_Int32, 0,
                                 RDAnnotationHelper(counter++));

      vkh::cmdPipelineBarrier(
          cmd, {
                   vkh::ImageMemoryBarrier(0, VK_ACCESS_TRANSFER_WRITE_BIT, VK_IMAGE_LAYOUT_UNDEFINED,
                                           VK_IMAGE_LAYOUT_GENERAL, offimgMS.image),
               });

      vkCmdClearColorImage(cmd, offimgMS.image, VK_IMAGE_LAYOUT_GENERAL,
                           vkh::ClearColorValue(0.2f, 0.2f, 0.2f, 1.0f), 1,
                           vkh::ImageSubresourceRange());

      rdoc->SetCommandAnnotation(RENDERDOC_DEVICEPOINTER_FROM_VKINSTANCE(instance), cmd,
                                 "global.counter", eRENDERDOC_Int32, 0,
                                 RDAnnotationHelper(counter++));

      rdoc->SetCommandAnnotation(RENDERDOC_DEVICEPOINTER_FROM_VKINSTANCE(instance), cmd,
                                 "renderpass.type", eRENDERDOC_String, 0,
                                 RDAnnotationHelper("boring"));

      vkCmdBeginRenderPass(
          cmd, vkh::RenderPassBeginInfo(mainWindow->rp, mainWindow->GetFB(), mainWindow->scissor),
          VK_SUBPASS_CONTENTS_INLINE);

      rdoc->SetCommandAnnotation(RENDERDOC_DEVICEPOINTER_FROM_VKINSTANCE(instance), cmd,
                                 "global.counter", eRENDERDOC_Int32, 0,
                                 RDAnnotationHelper(counter++));

      vkCmdBindPipeline(cmd, VK_PIPELINE_BIND_POINT_GRAPHICS, pipe);
      vkCmdSetViewport(cmd, 0, 1, &mainWindow->viewport);

      rdoc->SetCommandAnnotation(RENDERDOC_DEVICEPOINTER_FROM_VKINSTANCE(instance), cmd,
                                 "global.counter", eRENDERDOC_Int32, 0,
                                 RDAnnotationHelper(counter++));
      vkCmdSetScissor(cmd, 0, 1, &mainWindow->scissor);
      vkh::cmdBindVertexBuffers(cmd, 0, {vb.buffer}, {0});

      rdoc->SetCommandAnnotation(RENDERDOC_DEVICEPOINTER_FROM_VKINSTANCE(instance), cmd,
                                 "global.counter", eRENDERDOC_Int32, 0,
                                 RDAnnotationHelper(counter++));
      vkCmdDraw(cmd, 3, 1, 0, 0);

      rdoc->SetCommandAnnotation(RENDERDOC_DEVICEPOINTER_FROM_VKINSTANCE(instance), cmd,
                                 "global.counter", eRENDERDOC_Int32, 0,
                                 RDAnnotationHelper(counter++));

      vkCmdEndRenderPass(cmd);

      rdoc->SetCommandAnnotation(RENDERDOC_DEVICEPOINTER_FROM_VKINSTANCE(instance), cmd,
                                 "global.counter", eRENDERDOC_Int32, 0,
                                 RDAnnotationHelper(counter++));

      FinishUsingBackbuffer(cmd, VK_ACCESS_TRANSFER_WRITE_BIT, VK_IMAGE_LAYOUT_GENERAL);

      rdoc->SetCommandAnnotation(RENDERDOC_DEVICEPOINTER_FROM_VKINSTANCE(instance), cmd,
                                 "global.counter", eRENDERDOC_Int32, 0,
                                 RDAnnotationHelper(counter++));

      vkEndCommandBuffer(cmd);

      Submit(0, 1, {cmd});

      Present();
    }

    return 0;
  }
};

REGISTER_TEST();
